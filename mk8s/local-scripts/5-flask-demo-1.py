#!/usr/bin/env python3

"""
Here's what this script does:
1. Deploys a simple "Hello World" Flask application to the Karmada control plane.
2. Creates PropagationPolicies to distribute the app to all three member clusters.
3. Verifies that the Flask application pods become 'Running' on all member clusters.
4. Retrieves the service NodePort and creates unique LXD port-forwards for each cluster.
5. **Performs automated HTTP checks** to confirm each Flask instance is accessible and returns the correct content.
6. **Automatically cleans up** all demo resources (deployments, policies, services, and LXD devices).
"""

import os
import sys
import time
import json
import tempfile
import http.client

# Import shared configuration and helpers
from common import run_command, check_root_privileges, print_color, colors
from config import MEMBER_CLUSTERS, KARMADA_KUBECONFIG, CONFIG_FILES_DIR

# --- Configuration ---
# Use a new port range to avoid conflicts with other demos
APP_HOST_PORT_MAPPING = {
    "member1": "32101",
    "member2": "32102",
    "member3": "32103",
}

# --- Manifests ---
# Using a simple, public "Hello World" Flask image that listens on port 5000.
DEPLOYMENT_YAML = """
apiVersion: apps/v1
kind: Deployment
metadata:
  name: flask-demo
  labels:
    app: flask-demo
spec:
  replicas: 1
  selector:
    matchLabels:
      app: flask-demo
  template:
    metadata:
      labels:
        app: flask-demo
    spec:
      containers:
      - image: digitalocean/flask-helloworld:latest
        name: flask
        ports:
        - containerPort: 5000
"""

PROPAGATION_POLICY_YAML = f"""
apiVersion: policy.karmada.io/v1alpha1
kind: PropagationPolicy
metadata:
  name: flask-demo-propagation
spec:
  resourceSelectors:
    - apiVersion: apps/v1
      kind: Deployment
      name: flask-demo
  placement:
    clusterAffinity:
      clusterNames: {json.dumps(MEMBER_CLUSTERS)}
"""

# The service exposes the standard port 80 and targets the container's port 5000.
SERVICE_YAML = """
apiVersion: v1
kind: Service
metadata:
  name: flask-demo-service
spec:
  type: NodePort
  selector:
    app: flask-demo
  ports:
    - protocol: TCP
      port: 80
      targetPort: 5000
"""

SERVICE_POLICY_YAML = f"""
apiVersion: policy.karmada.io/v1alpha1
kind: PropagationPolicy
metadata:
  name: flask-demo-service-propagation
spec:
  resourceSelectors:
    - apiVersion: v1
      kind: Service
      name: flask-demo-service
  placement:
    clusterAffinity:
      clusterNames: {json.dumps(MEMBER_CLUSTERS)}
"""


def create_temp_file(content):
    """Creates a temporary file and returns its path."""
    with tempfile.NamedTemporaryFile(
        mode="w", delete=False, suffix=".yaml"
    ) as tmp_file:
        tmp_file.write(content)
        return tmp_file.name


def deploy_resources(karmada_env):
    """Deploys all necessary Kubernetes resources for the demo."""
    print_color(
        colors.YELLOW,
        "\n--- 1. Deploying Flask application and policies to Karmada ---",
    )

    dep_file = create_temp_file(DEPLOYMENT_YAML)
    dep_policy_file = create_temp_file(PROPAGATION_POLICY_YAML)
    svc_file = create_temp_file(SERVICE_YAML)
    svc_policy_file = create_temp_file(SERVICE_POLICY_YAML)

    created_files = [dep_file, dep_policy_file, svc_file, svc_policy_file]

    for f in created_files:
        run_command(["kubectl", "apply", "-f", f], env=karmada_env)

    return created_files


def verify_pod_readiness():
    """Waits for and verifies that all Flask pods are running in all member clusters."""
    print_color(
        colors.YELLOW, "\n--- 2. Verifying application propagation and pod status ---"
    )
    print(
        "--> Waiting up to 120 seconds for Flask pods to be running on all member clusters..."
    )

    for i in range(12):
        pods_ready_count = 0
        for member in MEMBER_CLUSTERS:
            kubeconfig_path = os.path.join(CONFIG_FILES_DIR, f"{member}.config")
            cmd = [
                "kubectl",
                "--kubeconfig",
                kubeconfig_path,
                "get",
                "pods",
                "-l",
                "app=flask-demo",
                "-o",
                "json",
            ]
            result = run_command(cmd, check=False, capture_output=True)
            if result.returncode == 0:
                pods = json.loads(result.stdout).get("items", [])
                running_pods = [
                    p for p in pods if p.get("status", {}).get("phase") == "Running"
                ]
                # Expecting 1 replica per cluster as defined in the deployment YAML
                if len(running_pods) == 1:
                    pods_ready_count += 1

        if pods_ready_count == len(MEMBER_CLUSTERS):
            print_color(
                colors.GREEN,
                "✅ SUCCESS: All Flask pods are running on all member clusters.",
            )
            return True

        print(
            f"Pods not ready yet (Ready clusters: {pods_ready_count}/{len(MEMBER_CLUSTERS)}). Retrying in 10s..."
        )
        time.sleep(10)

    print_color(
        colors.RED, "❌ FAILED: Timed out waiting for all Flask pods to become ready."
    )
    return False


def expose_services_and_get_nodeport():
    """Finds the service NodePort and creates LXD port forwards."""
    print_color(
        colors.YELLOW, "\n--- 3. Exposing application via LXD Port Forwarding ---"
    )

    member_to_check = MEMBER_CLUSTERS[0]
    kubeconfig_path = os.path.join(CONFIG_FILES_DIR, f"{member_to_check}.config")
    cmd = [
        "kubectl",
        "--kubeconfig",
        kubeconfig_path,
        "get",
        "service",
        "flask-demo-service",
        "-o",
        "json",
    ]
    print("--> Waiting for service to be created to get NodePort...")
    # It can take a moment for the service to be propagated and created
    for _ in range(6):
        result = run_command(cmd, capture_output=True, check=False)
        if result.returncode == 0:
            break
        time.sleep(10)
    else:
        print_color(colors.RED, "❌ FAILED: Could not find flask-demo-service.")
        return None

    service_info = json.loads(result.stdout)
    node_port = service_info["spec"]["ports"][0]["nodePort"]

    print(f"--> Service NodePort is {node_port}. Creating unique LXD proxy devices...")
    for member in MEMBER_CLUSTERS:
        host_port = APP_HOST_PORT_MAPPING[member]
        proxy_device_name = "proxy-flask"
        # Clean up old device first to ensure idempotency
        run_command(
            ["lxc", "config", "device", "remove", member, proxy_device_name],
            check=False,
        )
        proxy_command = [
            "lxc",
            "config",
            "device",
            "add",
            member,
            proxy_device_name,
            "proxy",
            f"listen=tcp:0.0.0.0:{host_port}",
            f"connect=tcp:127.0.0.1:{node_port}",
        ]
        run_command(proxy_command)

    return node_port


def verify_http_access():
    """Uses http.client to verify that each Flask endpoint is accessible and returns 'Hello World!'"""
    print_color(
        colors.YELLOW, "\n--- 4. Verifying HTTP access to all Flask instances ---"
    )
    all_accessible = True

    # Give the proxy a moment to stabilize
    time.sleep(5)

    for member, host_port in APP_HOST_PORT_MAPPING.items():
        print(
            f"--> Checking connection to Flask on {member} (http://127.0.0.1:{host_port})..."
        )
        try:
            conn = http.client.HTTPConnection("127.0.0.1", int(host_port), timeout=10)
            conn.request("GET", "/")
            response = conn.getresponse()
            body = response.read().decode("utf-8")

            if response.status == 200 and "Hello, World!" in body:
                print_color(
                    colors.GREEN,
                    f"  - ✅ SUCCESS: Received HTTP 200 OK with correct content.",
                )
            else:
                print_color(
                    colors.RED,
                    f"  - ❌ FAILED: Received status {response.status} with body: '{body}'",
                )
                all_accessible = False
            conn.close()
        except (http.client.HTTPException, ConnectionRefusedError, TimeoutError) as e:
            print_color(colors.RED, f"  - ❌ FAILED: Could not connect. Error: {e}")
            all_accessible = False

    return all_accessible


def cleanup_demo_resources(created_files):
    """Automatically cleans up all resources created by the demo script."""
    print_color(colors.YELLOW, "\n--- 5. Cleaning up all Flask demo resources ---")
    karmada_env = {"KUBECONFIG": KARMADA_KUBECONFIG}

    # Remove LXD proxy devices
    for member in MEMBER_CLUSTERS:
        run_command(
            ["lxc", "config", "device", "remove", member, "proxy-flask"], check=False
        )

    # Delete Kubernetes resources
    for f in reversed(created_files):  # Delete in reverse order
        if os.path.exists(f):
            run_command(
                ["kubectl", "delete", "-f", f, "--ignore-not-found=true"],
                env=karmada_env,
                check=False,
            )
            os.remove(f)

    print_color(colors.GREEN, "✅ Flask Demo cleanup complete.")


def main():
    """Orchestrates the deployment, verification, and cleanup of the Flask demo."""
    check_root_privileges("5-flask-demo.py")
    created_files = []
    all_tests_passed = False

    try:
        karmada_env = {"KUBECONFIG": KARMADA_KUBECONFIG}
        created_files = deploy_resources(karmada_env)

        if not verify_pod_readiness():
            sys.exit(1)

        node_port = expose_services_and_get_nodeport()
        if not node_port:
            sys.exit(1)

        if not verify_http_access():
            sys.exit(1)

        print_color(
            colors.GREEN,
            "\n\n✅ --- Flask Demo Completed and Verified Successfully! --- ✅",
        )
        all_tests_passed = True

    finally:
        if not all_tests_passed:
            print_color(
                colors.RED,
                "\nOne or more steps failed. Proceeding with cleanup...",
            )
        cleanup_demo_resources(created_files)


if __name__ == "__main__":
    main()
