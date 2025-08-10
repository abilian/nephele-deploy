#!/usr/bin/env python3

"""Here's what this script does:

1. **Checks for root privileges**: Ensures the script is run with sufficient permissions.
2. **Deploys an Nginx application across member clusters**: Creates a Deployment and Service in the Karmada control plane.
3. **Creates PropagationPolicies**: Ensures the Deployment and Service are propagated to all member clusters.
4. **Verifies pod readiness**: Waits for the Nginx pods to be Running on all member clusters.
5. **Finds the NodePort**: Retrieves the NodePort assigned to the Nginx Service.
6. **Displays access URLs**: Provides curl commands to access the Nginx welcome page from the host machine.
"""

import os
import sys
import time
import json
import tempfile

# Import shared configuration and helpers
from common import run_command, check_root_privileges, print_color, colors
from config import MEMBER_CLUSTERS, KARMADA_KUBECONFIG, CONFIG_FILES_DIR, PORT_MAPPING

# --- Manifests for the Nginx Demo ---

# This Deployment manifest is from the official Karmada samples.
# It will be created in the Karmada control plane.
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

# This PropagationPolicy tells Karmada to distribute the Deployment
# named 'nginx' to all member clusters.
PROPAGATION_POLICY_YAML = """
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
      clusterNames:
        - member1
        - member2
        - member3
"""

# This Service manifest will create a NodePort service, which exposes
# the Nginx deployment on a port on each member cluster's node.
# This is the key to making it accessible from the host.
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
      # By default, Kubernetes will assign a free port in the 30000-32767 range.
"""

# A separate policy is needed to propagate the Service to all clusters.
SERVICE_POLICY_YAML = """
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
      clusterNames:
        - member1
        - member2
        - member3
"""


def create_temp_file(content, suffix=".yaml"):
    """Creates a temporary file with the given content and returns its path."""
    with tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=suffix) as tmp_file:
        tmp_file.write(content)
        return tmp_file.name


def main():
    """Orchestrates the deployment and verification of the Nginx demo."""
    check_root_privileges("3-nginx-demo.py")

    karmada_env = {"KUBECONFIG": KARMADA_KUBECONFIG}

    # Create temporary files for all manifests
    dep_file = create_temp_file(DEPLOYMENT_YAML)
    dep_policy_file = create_temp_file(PROPAGATION_POLICY_YAML)
    svc_file = create_temp_file(SERVICE_YAML)
    svc_policy_file = create_temp_file(SERVICE_POLICY_YAML)

    try:
        # --- Step 1: Deploy the Application and Policies ---
        print_color(
            colors.YELLOW,
            "\n--- 1. Deploying Nginx application and policies to Karmada ---",
        )
        run_command(["kubectl", "apply", "-f", dep_file], env=karmada_env)
        run_command(["kubectl", "apply", "-f", dep_policy_file], env=karmada_env)
        run_command(["kubectl", "apply", "-f", svc_file], env=karmada_env)
        run_command(["kubectl", "apply", "-f", svc_policy_file], env=karmada_env)

        # --- Step 2: Verify Propagation and Pod Readiness ---
        print_color(
            colors.YELLOW,
            "\n--- 2. Verifying application propagation and pod status ---",
        )
        print(
            "--> Waiting up to 120 seconds for Nginx pods to be running on all member clusters..."
        )

        all_pods_ready = False
        for i in range(12):  # Wait up to 2 minutes
            pods_ready_count = 0
            for member in MEMBER_CLUSTERS:
                kubeconfig_path = os.path.join(CONFIG_FILES_DIR, f"{member}.config")
                # fmt: off
                cmd = [
                    "kubectl",
                    "--kubeconfig", kubeconfig_path,
                    "get", "pods",
                    "-l", "app=nginx",
                    "-o", "json",
                ]
                # fmt: on
                result = run_command(cmd, check=False, capture_output=True)

                if result.returncode == 0:
                    pods = json.loads(result.stdout).get("items", [])
                    running_pods = [
                        p for p in pods if p.get("status", {}).get("phase") == "Running"
                    ]
                    if len(running_pods) == 2:  # We expect 2 replicas
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

        # --- Step 3: Find the NodePort and Display Access URLs ---
        print_color(
            colors.YELLOW,
            "\n--- 3. Finding service NodePort and displaying access URLs ---",
        )

        # We only need to check one member cluster, as the NodePort will be the same across all of them.
        member_to_check = MEMBER_CLUSTERS[0]
        kubeconfig_path = os.path.join(CONFIG_FILES_DIR, f"{member_to_check}.config")
        # fmt: off
        cmd = [
            "kubectl",
            "--kubeconfig", kubeconfig_path,
            "get", "service", "nginx-service",
            "-o", "json",
        ]
        # fmt: on
        result = run_command(cmd, capture_output=True, env=karmada_env)

        service_info = json.loads(result.stdout)
        node_port = service_info["spec"]["ports"][0]["nodePort"]

        print_color(
            colors.GREEN,
            f"\n✅ Demo Deployed Successfully! Nginx is exposed on NodePort: {node_port}",
        )
        print("\nYou can now access the Nginx welcome page from your host machine.")
        print("To verify, run one of the following curl commands on the host:")

        for member, host_port in PORT_MAPPING.items():
            # Since the member cluster's node is the LXD container, its IP is localhost
            # and the port is the one we forwarded.
            print(f"\n  # To access Nginx on cluster '{member}':")
            print_color(colors.YELLOW, f"  curl http://127.0.0.1:{node_port}")

    finally:
        # --- Cleanup ---
        print_color(
            colors.YELLOW,
            "\n\n--- To clean up the demo resources, run the following commands ---",
        )
        print(f"export KUBECONFIG={KARMADA_KUBECONFIG}")
        print(f"kubectl delete -f {dep_file}")
        print(f"kubectl delete -f {dep_policy_file}")
        print(f"kubectl delete -f {svc_file}")
        print(f"kubectl delete -f {svc_policy_file}")


if __name__ == "__main__":
    main()
