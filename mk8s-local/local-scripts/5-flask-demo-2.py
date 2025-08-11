#!/usr/bin/env python3

"""
A simpler, more robust custom Flask demo.

Here's what this script does:
1. Builds a custom Flask application Docker image locally.
2. Saves the image to a .tar file.
3. Pushes the .tar file into each LXD container.
4. Imports the image directly into each member cluster's image cache.
5. Deploys the application, which now finds the image locally.
6. Verifies the deployment and performs HTTP checks.
7. Cleans up all resources, including the temporary .tar file and all cached images.
"""

import os
import sys
import time
import json
import tempfile
import http.client

# Import shared configuration and helpers
from common import run_command, check_root_privileges, print_color, colors
from config import (
    MEMBER_CLUSTERS,
    KARMADA_KUBECONFIG,
    CONFIG_FILES_DIR,
)

# --- Configuration ---
APP_HOST_PORT_MAPPING = {
    "member1": "32301",
    "member2": "32302",
    "member3": "32303",
}
APP_BUILD_CONTEXT = "./custom-flask-app"
# A simple image name, no registry prefix needed.
CUSTOM_IMAGE_NAME = "custom-flask-app:latest"
APP_NAME = "custom-flask-demo-simple"
PROXY_DEVICE_NAME = "proxy-simple-flask"


def create_temp_file(content):
    """Creates a temporary file and returns its path."""
    with tempfile.NamedTemporaryFile(
        mode="w", delete=False, suffix=".yaml"
    ) as tmp_file:
        tmp_file.write(content)
        return tmp_file.name


def build_and_save_image_locally():
    """Builds the Docker image and saves it to a temporary tar file."""
    print_color(colors.YELLOW, f"\n--- 1. Building and Saving Image: {CUSTOM_IMAGE_NAME} ---")
    if not os.path.isdir(APP_BUILD_CONTEXT):
        print_color(colors.RED, f"FATAL: App build directory not found at '{APP_BUILD_CONTEXT}'.")
        sys.exit(1)

    print(f"--> Building image with tag: {CUSTOM_IMAGE_NAME}")
    run_command(["docker", "build", "-t", CUSTOM_IMAGE_NAME, APP_BUILD_CONTEXT])

    temp_tar_file = tempfile.NamedTemporaryFile(delete=False, suffix=".tar")
    temp_tar_path = temp_tar_file.name
    temp_tar_file.close()

    print(f"--> Saving image to tarball: {temp_tar_path}")
    run_command(["docker", "save", "-o", temp_tar_path, CUSTOM_IMAGE_NAME])

    print_color(colors.GREEN, "✅ Image built and saved successfully.")
    return temp_tar_path


def distribute_and_import_image(image_tar_path):
    """Pushes the image tarball to each member cluster and imports it."""
    print_color(colors.YELLOW, "\n--- 2. Distributing Image to Member Clusters ---")
    remote_path = f"/root/{os.path.basename(image_tar_path)}"

    for member in MEMBER_CLUSTERS:
        print(f"--> Processing cluster: {member}")
        print(f"    - Pushing '{image_tar_path}' to '{member}:{remote_path}'...")
        run_command(["lxc", "file", "push", image_tar_path, f"{member}{remote_path}"])

        print(f"    - Importing image from '{remote_path}' into the cluster's cache...")
        run_command(["lxc", "exec", member, "--", "microk8s", "images", "import", remote_path])

    print_color(colors.GREEN, "✅ Image distributed to all member clusters.")


def deploy_resources(karmada_env):
    """Deploys all necessary Kubernetes resources for the demo."""
    print_color(colors.YELLOW, f"\n--- 3. Deploying '{APP_NAME}' to Karmada ---")
    deployment_yaml = f"""
apiVersion: apps/v1
kind: Deployment
metadata:
  name: {APP_NAME}
  labels:
    app: {APP_NAME}
spec:
  replicas: 1
  selector:
    matchLabels:
      app: {APP_NAME}
  template:
    metadata:
      labels:
        app: {APP_NAME}
    spec:
      containers:
      - image: {CUSTOM_IMAGE_NAME}
        name: flask
        imagePullPolicy: IfNotPresent
        ports:
        - containerPort: 5000
"""
    propagation_policy_yaml = f"""
apiVersion: policy.karmada.io/v1alpha1
kind: PropagationPolicy
metadata:
  name: {APP_NAME}-propagation
spec:
  resourceSelectors:
    - apiVersion: apps/v1
      kind: Deployment
      name: {APP_NAME}
  placement:
    clusterAffinity:
      clusterNames: {json.dumps(MEMBER_CLUSTERS)}
"""
    service_yaml = f"""
apiVersion: v1
kind: Service
metadata:
  name: {APP_NAME}-service
spec:
  type: NodePort
  selector:
    app: {APP_NAME}
  ports:
    - protocol: TCP
      port: 80
      targetPort: 5000
"""
    service_policy_yaml = f"""
apiVersion: policy.karmada.io/v1alpha1
kind: PropagationPolicy
metadata:
  name: {APP_NAME}-service-propagation
spec:
  resourceSelectors:
    - apiVersion: v1
      kind: Service
      name: {APP_NAME}-service
  placement:
    clusterAffinity:
      clusterNames: {json.dumps(MEMBER_CLUSTERS)}
"""
    files = [
        create_temp_file(deployment_yaml),
        create_temp_file(propagation_policy_yaml),
        create_temp_file(service_yaml),
        create_temp_file(service_policy_yaml),
    ]
    for f in files:
        run_command(["kubectl", "apply", "-f", f], env=karmada_env)
    return files


def verify_pod_readiness():
    """Waits for and verifies that all pods are running in all member clusters."""
    print_color(colors.YELLOW, "\n--- 4. Verifying pod readiness ---")
    print("--> Waiting up to 120 seconds for pods to be running...")
    for i in range(12):
        ready_count = 0
        for member in MEMBER_CLUSTERS:
            kubeconfig = os.path.join(CONFIG_FILES_DIR, f"{member}.config")
            cmd = ["kubectl", "--kubeconfig", kubeconfig, "get", "pods", "-l", f"app={APP_NAME}", "-o", "json"]
            result = run_command(cmd, check=False, capture_output=True)
            if result.returncode == 0:
                pods = json.loads(result.stdout).get("items", [])
                running = [p for p in pods if p.get("status", {}).get("phase") == "Running"]
                if len(running) == 1:
                    ready_count += 1
        if ready_count == len(MEMBER_CLUSTERS):
            print_color(colors.GREEN, "✅ SUCCESS: All pods are running.")
            return True
        print(f"Pods not ready yet ({ready_count}/{len(MEMBER_CLUSTERS)}). Retrying in 10s...")
        time.sleep(10)
    print_color(colors.RED, "❌ FAILED: Timed out waiting for pods to become ready.")
    return False


def expose_services_and_get_nodeport():
    """Finds the service NodePort and creates LXD port forwards."""
    print_color(colors.YELLOW, "\n--- 5. Exposing application via LXD Port Forwarding ---")
    kubeconfig = os.path.join(CONFIG_FILES_DIR, f"{MEMBER_CLUSTERS[0]}.config")
    cmd = ["kubectl", "--kubeconfig", kubeconfig, "get", "service", f"{APP_NAME}-service", "-o", "json"]
    for _ in range(6):
        result = run_command(cmd, capture_output=True, check=False)
        if result.returncode == 0:
            break
        time.sleep(10)
    else:
        print_color(colors.RED, "❌ FAILED: Could not find the service.")
        return None
    node_port = json.loads(result.stdout)["spec"]["ports"][0]["nodePort"]
    print(f"--> Service NodePort is {node_port}. Creating LXD proxy devices...")
    for member, host_port in APP_HOST_PORT_MAPPING.items():
        run_command(["lxc", "config", "device", "remove", member, PROXY_DEVICE_NAME], check=False)
        run_command(["lxc", "config", "device", "add", member, PROXY_DEVICE_NAME, "proxy", f"listen=tcp:0.0.0.0:{host_port}", f"connect=tcp:127.0.0.1:{node_port}"])
    return node_port


def verify_http_access():
    """Verifies that each Nginx endpoint is accessible and returns HTTP 200."""
    print_color(colors.YELLOW, "\n--- 6. Verifying HTTP access to all instances ---")
    all_ok = True
    time.sleep(5)
    for member, host_port in APP_HOST_PORT_MAPPING.items():
        print(f"--> Checking connection to {member} (http://127.0.0.1:{host_port})...")
        try:
            conn = http.client.HTTPConnection("127.0.0.1", int(host_port), timeout=10)
            conn.request("GET", "/")
            response = conn.getresponse()
            body = response.read().decode()
            if response.status == 200 and "Hello from our Custom Flask App" in body:
                print_color(colors.GREEN, f"  - ✅ SUCCESS: Received HTTP 200. Body contains expected text.")
            else:
                print_color(colors.RED, f"  - ❌ FAILED: Status {response.status}, Body: '{body}'")
                all_ok = False
            conn.close()
        except Exception as e:
            print_color(colors.RED, f"  - ❌ FAILED: Could not connect. Error: {e}")
            all_ok = False
    return all_ok


def cleanup_demo_resources(created_files, image_tar_path):
    """Cleans up all resources created by the demo script."""
    print_color(colors.YELLOW, "\n--- 7. Cleaning up all demo resources ---")
    karmada_env = {"KUBECONFIG": KARMADA_KUBECONFIG}
    # Delete Kubernetes resources
    for f in reversed(created_files):
        if os.path.exists(f):
            run_command(["kubectl", "delete", "-f", f, "--ignore-not-found=true"], env=karmada_env, check=False)
            os.remove(f)
    # Remove LXD proxy devices
    for member in MEMBER_CLUSTERS:
        run_command(["lxc", "config", "device", "remove", member, PROXY_DEVICE_NAME], check=False)
        print(f"--> Removing cached image from {member}...")
        run_command(["lxc", "exec", member, "--", "microk8s", "images", "rm", CUSTOM_IMAGE_NAME], check=False)
    # Remove local tar file
    if image_tar_path and os.path.exists(image_tar_path):
        print(f"--> Removing temporary image tarball: {image_tar_path}")
        os.remove(image_tar_path)
    # Remove image from host Docker cache
    print(f"--> Removing image from local Docker cache: {CUSTOM_IMAGE_NAME}")
    run_command(["docker", "image", "rm", CUSTOM_IMAGE_NAME], check=False)
    print_color(colors.GREEN, "✅ Demo cleanup complete.")


def main():
    """Orchestrates the entire simplified custom demo workflow."""
    check_root_privileges("7-custom-flask-demo-simple.py")
    image_tar_path = None
    created_files = []
    all_tests_passed = False

    try:
        image_tar_path = build_and_save_image_locally()
        distribute_and_import_image(image_tar_path)

        karmada_env = {"KUBECONFIG": KARMADA_KUBECONFIG}
        created_files = deploy_resources(karmada_env)

        if not verify_pod_readiness(): sys.exit(1)
        if not expose_services_and_get_nodeport(): sys.exit(1)
        if not verify_http_access(): sys.exit(1)

        print_color(colors.GREEN, "\n\n✅ --- Simple Custom Flask Demo Completed Successfully! --- ✅")
        all_tests_passed = True

    finally:
        if not all_tests_passed:
            print_color(colors.RED, "\nOne or more steps failed. Proceeding with cleanup...")
        cleanup_demo_resources(created_files, image_tar_path)


if __name__ == "__main__":
    main()
