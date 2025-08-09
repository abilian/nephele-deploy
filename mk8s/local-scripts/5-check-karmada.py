#!/usr/bin/env python3

import os
import sys
import subprocess
import json
import time
import tempfile
import shutil
import argparse  # Import the argument parsing library

# --- Configuration ---
MEMBER_CLUSTERS_TO_DEPLOY = ["member1", "member2"]
MEMBER_CLUSTER_TO_AVOID = "member3"
ALL_MEMBER_CLUSTERS = MEMBER_CLUSTERS_TO_DEPLOY + [MEMBER_CLUSTER_TO_AVOID]

KARMADA_NAMESPACE = "karmada-system"
KARMADA_KUBECONFIG = os.path.expanduser("~/.kube/karmada.config")


# --- ANSI Color Codes for Better Output ---
class colors:
    GREEN = "\033[92m"
    RED = "\033[91m"
    YELLOW = "\033[93m"
    BLUE = "\033[94m"
    ENDC = "\033[0m"


def print_color(color, message):
    """Prints a message in a given color."""
    print(f"{color}{message}{colors.ENDC}")


# --- Helper Functions ---


def run_command(command, check=True, capture_output=False, env=None):
    """A helper to run a shell command and handle errors."""
    print_color(colors.BLUE, f"--> Executing: {' '.join(command)}")
    try:
        process_env = os.environ.copy()
        if env:
            process_env.update(env)

        result = subprocess.run(
            command,
            check=check,
            capture_output=capture_output,
            text=True,
            env=process_env,
        )
        return result
    except FileNotFoundError:
        print_color(
            colors.RED,
            f"Error: Command '{command[0]}' not found. Is it installed and in your PATH?",
        )
        sys.exit(1)
    except subprocess.CalledProcessError as e:
        if not check:
            return e
        print_color(colors.RED, f"Error executing command: {' '.join(command)}")
        print_color(colors.RED, f"Return code: {e.returncode}")
        if e.stdout:
            print(f"Stdout:\n{e.stdout}")
        if e.stderr:
            print(f"Stderr:\n{e.stderr}")
        sys.exit(1)


def check_dependencies(config_dir):
    """Checks if required CLI tools and config files are present."""
    print("--- Checking for required tools and files ---")
    if not shutil.which("kubectl"):
        print_color(
            colors.RED, "FATAL: 'kubectl' command not found. Please install it first."
        )
        sys.exit(1)

    if not os.path.exists(KARMADA_KUBECONFIG):
        print_color(
            colors.RED,
            f"FATAL: Karmada kubeconfig not found at '{KARMADA_KUBECONFIG}'.",
        )
        sys.exit(1)

    for member in ALL_MEMBER_CLUSTERS:
        # Check for config files in the directory provided by the user.
        config_path = os.path.join(config_dir, f"{member}.config")
        if not os.path.exists(config_path):
            print_color(
                colors.RED,
                f"FATAL: Kubeconfig for '{member}' not found at '{config_path}'.",
            )
            print_color(
                colors.YELLOW,
                f"       Please specify the correct directory using the --config-dir argument.",
            )
            sys.exit(1)

    print_color(colors.GREEN, "All dependencies found.")
    return True


# --- Verification Logic (check_control_plane_health and check_member_cluster_status are unchanged) ---


def check_control_plane_health():
    """Level 1: Verifies all Karmada control plane pods are Running and Ready."""
    print_color(
        colors.YELLOW, "\n--- Level 1: Checking Karmada Control Plane Health ---"
    )

    env = {"KUBECONFIG": KARMADA_KUBECONFIG}
    result = run_command(
        ["kubectl", "get", "pods", "-n", KARMADA_NAMESPACE, "-o", "json"],
        capture_output=True,
        env=env,
    )

    all_pods_ready = True
    pods_data = json.loads(result.stdout)

    if not pods_data.get("items"):
        print_color(
            colors.RED, f"❌ FAILED: No pods found in namespace '{KARMADA_NAMESPACE}'."
        )
        return False

    for pod in pods_data["items"]:
        pod_name = pod["metadata"]["name"]
        pod_status = pod["status"]["phase"]

        if pod_status != "Running":
            print_color(
                colors.RED, f"  - Pod '{pod_name}' is not running. Status: {pod_status}"
            )
            all_pods_ready = False
            continue

        all_containers_ready = True
        for container_status in pod["status"].get("containerStatuses", []):
            if not container_status["ready"]:
                all_containers_ready = False
                break

        if all_containers_ready:
            print_color(colors.GREEN, f"  - Pod '{pod_name}' is Running and Ready.")
        else:
            print_color(
                colors.RED,
                f"  - Pod '{pod_name}' is Running but not all containers are Ready.",
            )
            all_pods_ready = False

    if all_pods_ready:
        print_color(colors.GREEN, "✅ SUCCESS: All control plane pods are healthy.")
    else:
        print_color(
            colors.RED, "❌ FAILED: One or more control plane pods are not healthy."
        )

    return all_pods_ready


def check_member_cluster_status():
    """Level 2: Verifies all member clusters are registered and Ready."""
    print_color(colors.YELLOW, "\n--- Level 2: Checking Member Cluster Status ---")

    env = {"KUBECONFIG": KARMADA_KUBECONFIG}
    result = run_command(
        ["kubectl", "get", "clusters", "-o", "json"], capture_output=True, env=env
    )

    all_clusters_ready = True
    clusters_data = json.loads(result.stdout)
    found_clusters = {
        item["metadata"]["name"] for item in clusters_data.get("items", [])
    }

    for member_name in ALL_MEMBER_CLUSTERS:
        if member_name not in found_clusters:
            print_color(
                colors.RED,
                f"  - Cluster '{member_name}' is not registered with Karmada.",
            )
            all_clusters_ready = False
            continue

        cluster_item = next(
            (
                item
                for item in clusters_data["items"]
                if item["metadata"]["name"] == member_name
            ),
            None,
        )
        is_ready = False
        for condition in cluster_item.get("status", {}).get("conditions", []):
            if condition.get("type") == "Ready" and condition.get("status") == "True":
                is_ready = True
                break

        if is_ready:
            print_color(colors.GREEN, f"  - Cluster '{member_name}' is Ready.")
        else:
            print_color(colors.RED, f"  - Cluster '{member_name}' is not Ready.")
            all_clusters_ready = False

    if all_clusters_ready:
        print_color(
            colors.GREEN, "✅ SUCCESS: All member clusters are registered and ready."
        )
    else:
        print_color(colors.RED, "❌ FAILED: One or more member clusters are not ready.")

    return all_clusters_ready


def check_e2e_deployment(config_dir):
    """Level 3: Deploys a test application and verifies its propagation."""
    print_color(
        colors.YELLOW, "\n--- Level 3: Performing End-to-End Functionality Test ---"
    )

    karmada_env = {"KUBECONFIG": KARMADA_KUBECONFIG}

    deployment_yaml = """
apiVersion: apps/v1
kind: Deployment
metadata:
  name: karmada-test-nginx
  labels:
    app: karmada-test
spec:
  replicas: 2
  selector:
    matchLabels:
      app: karmada-test
  template:
    metadata:
      labels:
        app: karmada-test
    spec:
      containers:
      - name: nginx
        image: nginx:1.21.6
"""

    policy_yaml = f"""
apiVersion: policy.karmada.io/v1alpha1
kind: PropagationPolicy
metadata:
  name: karmada-test-nginx-policy
spec:
  resourceSelectors:
    - apiVersion: apps/v1
      kind: Deployment
      name: karmada-test-nginx
  placement:
    clusterAffinity:
      clusterNames: {MEMBER_CLUSTERS_TO_DEPLOY}
"""

    dep_filename, pol_filename = "", ""
    try:
        with (
            tempfile.NamedTemporaryFile(
                mode="w", delete=False, suffix=".yaml"
            ) as dep_file,
            tempfile.NamedTemporaryFile(
                mode="w", delete=False, suffix=".yaml"
            ) as pol_file,
        ):
            dep_file.write(deployment_yaml)
            dep_filename = dep_file.name
            pol_file.write(policy_yaml)
            pol_filename = pol_file.name

        print("--> Deploying test Nginx application and propagation policy...")
        run_command(["kubectl", "apply", "-f", dep_filename], env=karmada_env)
        run_command(["kubectl", "apply", "-f", pol_filename], env=karmada_env)

        print("--> Waiting up to 90 seconds for resources to be deployed...")
        time.sleep(90)

        overall_success = True

        for member in MEMBER_CLUSTERS_TO_DEPLOY:
            print(f"--> Verifying deployment on '{member}'...")
            member_kubeconfig_path = os.path.join(config_dir, f"{member}.config")
            member_env = {"KUBECONFIG": member_kubeconfig_path}
            result = run_command(
                ["kubectl", "get", "pods", "-l", "app=karmada-test", "-o", "json"],
                capture_output=True,
                env=member_env,
            )
            pods = json.loads(result.stdout).get("items", [])
            running_pods = [p for p in pods if p["status"]["phase"] == "Running"]

            if len(running_pods) == 2:
                print_color(
                    colors.GREEN, f"  - SUCCESS: Found 2 running pods on '{member}'."
                )
            else:
                print_color(
                    colors.RED,
                    f"  - FAILED: Expected 2 running pods on '{member}', but found {len(running_pods)}.",
                )
                overall_success = False

        print(f"--> Verifying deployment is absent from '{MEMBER_CLUSTER_TO_AVOID}'...")
        avoid_kubeconfig_path = os.path.join(
            config_dir, f"{MEMBER_CLUSTER_TO_AVOID}.config"
        )
        avoid_env = {"KUBECONFIG": avoid_kubeconfig_path}
        result = run_command(
            ["kubectl", "get", "pods", "-l", "app=karmada-test", "-o", "json"],
            capture_output=True,
            env=avoid_env,
        )
        pods = json.loads(result.stdout).get("items", [])

        if len(pods) == 0:
            print_color(
                colors.GREEN,
                f"  - SUCCESS: No test pods found on '{MEMBER_CLUSTER_TO_AVOID}', as expected.",
            )
        else:
            print_color(
                colors.RED,
                f"  - FAILED: Found {len(pods)} test pods on '{MEMBER_CLUSTER_TO_AVOID}', but expected 0.",
            )
            overall_success = False

        if overall_success:
            print_color(colors.GREEN, "\n✅ SUCCESS: End-to-end test passed.")
        else:
            print_color(colors.RED, "\n❌ FAILED: End-to-end test failed.")

        return overall_success

    finally:
        print_color(colors.YELLOW, "\n--- Cleaning up test resources ---")
        if dep_filename:
            run_command(
                ["kubectl", "delete", "-f", dep_filename], env=karmada_env, check=False
            )
            os.remove(dep_filename)
        if pol_filename:
            run_command(
                ["kubectl", "delete", "-f", pol_filename], env=karmada_env, check=False
            )
            os.remove(pol_filename)


def main():
    """Main function to run all checks."""
    parser = argparse.ArgumentParser(
        description="Verify the health and functionality of a Karmada deployment."
    )
    parser.add_argument(
        "--config-dir",
        default="/root",
        help="Directory containing the member cluster kubeconfig files (e.g., member1.config). Default is /root.",
    )
    args = parser.parse_args()

    if not check_dependencies(args.config_dir):
        sys.exit(1)

    results = {
        "control_plane": check_control_plane_health(),
        "member_clusters": check_member_cluster_status(),
        "e2e_deployment": False,
    }

    if all(results.values()):
        results["e2e_deployment"] = check_e2e_deployment(args.config_dir)
    else:
        print_color(
            colors.RED,
            "\nSkipping Level 3 (End-to-End Test) due to failures in preliminary checks.",
        )

    print("\n\n" + "=" * 20 + " FINAL SUMMARY " + "=" * 20)
    if all(results.values()):
        print_color(
            colors.GREEN, "✅ All Karmada verification checks passed successfully!"
        )
    else:
        print_color(colors.RED, "❌ One or more Karmada verification checks failed.")
    print("=" * 55)


if __name__ == "__main__":
    main()
