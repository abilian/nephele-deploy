#!/usr/bin/env python3

"""
Here's what this script does:
1. Deploys an Nginx application and policies to the Karmada control plane.
2. Verifies that the Nginx pods become 'Running' on all member clusters.
3. Retrieves the service NodePort and creates unique LXD port-forwards for each cluster.
4. **Performs automated HTTP checks** to confirm each Nginx instance is accessible.
5. **Automatically cleans up** all demo resources (deployments, policies, services, and LXD devices).
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
APP_HOST_PORT_MAPPING = {
    "member1": "32001",
    "member2": "32002",
    "member3": "32003",
}

# --- Manifests ---
DEPLOYMENT_YAML = """
apiVersion: apps/v1
kind: Deployment
metadata:
  name: nginx-demo
  labels:
    app: nginx-demo
spec:
  replicas: 2
  selector:
    matchLabels:
      app: nginx-demo
  template:
    metadata:
      labels:
        app: nginx-demo
    spec:
      containers:
      - image: nginx
        name: nginx
"""

PROPAGATION_POLICY_YAML = f"""
apiVersion: policy.karmada.io/v1alpha1
kind: PropagationPolicy
metadata:
  name: nginx-demo-propagation
spec:
  resourceSelectors:
    - apiVersion: apps/v1
      kind: Deployment
      name: nginx-demo
  placement:
    clusterAffinity:
      clusterNames: {MEMBER_CLUSTERS}
"""

SERVICE_YAML = """
apiVersion: v1
kind: Service
metadata:
  name: nginx-demo-service
spec:
  type: NodePort
  selector:
    app: nginx-demo
  ports:
    - protocol: TCP
      port: 80
      targetPort: 80
"""

SERVICE_POLICY_YAML = f"""
apiVersion: policy.karmada.io/v1alpha1
kind: PropagationPolicy
metadata:
  name: nginx-demo-service-propagation
spec:
  resourceSelectors:
    - apiVersion: v1
      kind: Service
      name: nginx-demo-service
  placement:
    clusterAffinity:
      clusterNames: {MEMBER_CLUSTERS}
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
        "\n--- 1. Deploying Nginx application and policies to Karmada ---",
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
    """Waits for and verifies that all Nginx pods are running in all member clusters."""
    print_color(
        colors.YELLOW, "\n--- 2. Verifying application propagation and pod status ---"
    )
    print(
        "--> Waiting up to 120 seconds for Nginx pods to be running on all member clusters..."
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
                "app=nginx-demo",
                "-o",
                "json",
            ]
            result = run_command(cmd, check=False, capture_output=True)
            if result.returncode == 0:
                pods = json.loads(result.stdout).get("items", [])
                running_pods = [
                    p for p in pods if p.get("status", {}).get("phase") == "Running"
                ]
                if len(running_pods) == 2:
                    pods_ready_count += 1

        if pods_ready_count == len(MEMBER_CLUSTERS):
            print_color(
                colors.GREEN,
                "✅ SUCCESS: All Nginx pods are running on all member clusters.",
            )
            return True

        print(
            f"Pods not ready yet (Ready clusters: {pods_ready_count}/{len(MEMBER_CLUSTERS)}). Retrying in 10s..."
        )
        time.sleep(10)

    print_color(
        colors.RED, "❌ FAILED: Timed out waiting for all Nginx pods to become ready."
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
        "nginx-demo-service",
        "-o",
        "json",
    ]
    result = run_command(cmd, capture_output=True)

    service_info = json.loads(result.stdout)
    node_port = service_info["spec"]["ports"][0]["nodePort"]

    print(f"--> Service NodePort is {node_port}. Creating unique LXD proxy devices...")
    for member in MEMBER_CLUSTERS:
        host_port = APP_HOST_PORT_MAPPING[member]
        proxy_device_name = "proxy-nginx"
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
    """Uses http.client to verify that each Nginx endpoint is accessible and returns HTTP 200."""
    print_color(
        colors.YELLOW, "\n--- 4. Verifying HTTP access to all Nginx instances ---"
    )
    all_accessible = True

    for member, host_port in APP_HOST_PORT_MAPPING.items():
        print(
            f"--> Checking connection to Nginx on {member} (http://127.0.0.1:{host_port})..."
        )
        try:
            conn = http.client.HTTPConnection("127.0.0.1", int(host_port), timeout=10)
            conn.request("GET", "/")
            response = conn.getresponse()
            if response.status == 200:
                print_color(
                    colors.GREEN, f"  - ✅ SUCCESS: Received HTTP {response.status} OK."
                )
            else:
                print_color(
                    colors.RED,
                    f"  - ❌ FAILED: Received unexpected status HTTP {response.status}.",
                )
                all_accessible = False
            conn.close()
        except (http.client.HTTPException, ConnectionRefusedError, TimeoutError) as e:
            print_color(colors.RED, f"  - ❌ FAILED: Could not connect. Error: {e}")
            all_accessible = False

    return all_accessible


def cleanup_demo_resources(created_files):
    """Automatically cleans up all resources created by the demo script."""
    print_color(colors.YELLOW, "\n--- 5. Cleaning up all demo resources ---")
    karmada_env = {"KUBECONFIG": KARMADA_KUBECONFIG}

    # Remove LXD proxy devices
    for member in MEMBER_CLUSTERS:
        run_command(
            ["lxc", "config", "device", "remove", member, "proxy-nginx"], check=False
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

    print_color(colors.GREEN, "✅ Demo cleanup complete.")


def main():
    """Orchestrates the deployment, verification, and cleanup of the Nginx demo."""
    check_root_privileges("4-nginx-demo.py")
    created_files = []

    try:
        created_files = deploy_resources({"KUBECONFIG": KARMADA_KUBECONFIG})

        if not verify_pod_readiness():
            sys.exit(1)

        expose_services_and_get_nodeport()

        if not verify_http_access():
            sys.exit(1)

        print_color(
            colors.GREEN,
            "\n\n✅ --- Nginx Demo Completed and Verified Successfully! --- ✅",
        )

    finally:
        cleanup_demo_resources(created_files)


if __name__ == "__main__":
    main()
