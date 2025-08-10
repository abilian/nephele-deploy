#!/usr/bin/env python3

"""
Here's what this script does:
1. Deploys an Nginx application (Deployment and Service) to the Karmada control plane.
2. Creates PropagationPolicies to distribute the app to all member clusters.
3. Verifies that the Nginx pods become 'Running' on all member clusters.
4. Retrieves the dynamically assigned NodePort for the Nginx service.
5. **Dynamically creates unique LXD port-forwards** for each cluster to expose the NodePort on the host.
6. Displays the final, working curl commands to access the Nginx welcome page.
7. Provides cleanup instructions.
"""

import os
import sys
import time
import json
import tempfile

# Import shared configuration and helpers
from common import run_command, check_root_privileges, print_color, colors
from config import MEMBER_CLUSTERS, KARMADA_KUBECONFIG, CONFIG_FILES_DIR

# --- NEW: Define a unique mapping for the application's NodePort on the host ---
APP_HOST_PORT_MAPPING = {
    "member1": "32001",
    "member2": "32002",
    "member3": "32003",
}

# --- Manifests for the Nginx Demo ---
DEPLOYMENT_YAML = """
apiVersion: apps/v1
kind: Deployment
metadata:
  name: nginx
  labels:
    app: nginx
spec:
  replicas: 2
  selector:
    matchLabels:
      app: nginx
  template:
    metadata:
      labels:
        app: nginx
    spec:
      containers:
      - image: nginx
        name: nginx
"""

PROPAGATION_POLICY_YAML = f"""
apiVersion: policy.karmada.io/v1alpha1
kind: PropagationPolicy
metadata:
  name: nginx-propagation
spec:
  resourceSelectors:
    - apiVersion: apps/v1
      kind: Deployment
      name: nginx
  placement:
    clusterAffinity:
      clusterNames: {MEMBER_CLUSTERS}
"""

SERVICE_YAML = """
apiVersion: v1
kind: Service
metadata:
  name: nginx-service
spec:
  type: NodePort
  selector:
    app: nginx
  ports:
    - protocol: TCP
      port: 80
      targetPort: 80
"""

SERVICE_POLICY_YAML = f"""
apiVersion: policy.karmada.io/v1alpha1
kind: PropagationPolicy
metadata:
  name: nginx-service-propagation
spec:
  resourceSelectors:
    - apiVersion: v1
      kind: Service
      name: nginx-service
  placement:
    clusterAffinity:
      clusterNames: {MEMBER_CLUSTERS}
"""


def create_temp_file(content, suffix=".yaml"):
    """Creates a temporary file with the given content and returns its path."""
    with tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=suffix) as tmp_file:
        tmp_file.write(content)
        return tmp_file.name


def main():
    """Orchestrates the deployment and verification of the Nginx demo."""
    check_root_privileges("4-nginx-demo.py")
    karmada_env = {"KUBECONFIG": KARMADA_KUBECONFIG}

    dep_file = create_temp_file(DEPLOYMENT_YAML)
    dep_policy_file = create_temp_file(PROPAGATION_POLICY_YAML)
    svc_file = create_temp_file(SERVICE_YAML)
    svc_policy_file = create_temp_file(SERVICE_POLICY_YAML)

    # Store created resources for robust cleanup
    created_files = [dep_file, dep_policy_file, svc_file, svc_policy_file]
    node_port = None

    try:
        # --- Step 1: Deploy the Application and Policies ---
        print_color(
            colors.YELLOW,
            "\n--- 1. Deploying Nginx application and policies to Karmada ---",
        )
        for f in created_files:
            run_command(["kubectl", "apply", "-f", f], env=karmada_env)

        # --- Step 2: Verify Propagation and Pod Readiness ---
        print_color(
            colors.YELLOW,
            "\n--- 2. Verifying application propagation and pod status ---",
        )
        print(
            "--> Waiting up to 120 seconds for Nginx pods to be running on all member clusters..."
        )
        all_pods_ready = False
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
                    "app=nginx",
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
                all_pods_ready = True
                break
            print(
                f"Pods not ready yet (Ready clusters: {pods_ready_count}/{len(MEMBER_CLUSTERS)}). Retrying in 10s..."
            )
            time.sleep(10)
        if not all_pods_ready:
            print_color(
                colors.RED,
                "❌ FAILED: Timed out waiting for all Nginx pods to become ready.",
            )
            sys.exit(1)

        # --- Step 3: Find the NodePort and Create Port Forwards ---
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
            "nginx-service",
            "-o",
            "json",
        ]
        result = run_command(cmd, capture_output=True)

        service_info = json.loads(result.stdout)
        node_port = service_info["spec"]["ports"][0]["nodePort"]

        print(
            f"--> Service NodePort is {node_port}. Creating unique LXD proxy devices for each cluster..."
        )
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
                f"listen=tcp:0.0.0.0:{host_port}",  # Listen on a UNIQUE host port
                f"connect=tcp:127.0.0.1:{node_port}",  # Connect to the SHARED container NodePort
            ]
            run_command(proxy_command)

        print_color(colors.GREEN, f"\n✅ Demo Deployed and Exposed Successfully!")
        print(
            "\nYou can now access the Nginx welcome page from your host machine via each member cluster."
        )
        print("To verify, run the following curl commands on the host:")
        for member in MEMBER_CLUSTERS:
            host_port = APP_HOST_PORT_MAPPING[member]
            print(f"\n  # To access Nginx on cluster '{member}':")
            print_color(colors.YELLOW, f"  curl http://127.0.0.1:{host_port}")

    finally:
        # --- Cleanup ---
        print_color(
            colors.YELLOW,
            "\n\n--- To clean up the demo resources, run the following commands ---",
        )
        if node_port:
            for member in MEMBER_CLUSTERS:
                print(f"lxc config device remove {member} proxy-nginx")
        print(f"export KUBECONFIG={KARMADA_KUBECONFIG}")
        for f in created_files:
            if os.path.exists(f):
                print(f"kubectl delete -f {f}")
                os.remove(f)


if __name__ == "__main__":
    main()
