#!/usr/bin/env python3

import json
import os
import sys
import tempfile
import time

from common import run_command, check_root_privileges, print_color, colors

# Define which clusters to test deployment on
MEMBER_CLUSTERS_TO_DEPLOY = ["member1", "member2"]
MEMBER_CLUSTER_TO_AVOID = "member3"


def check_dependencies():
    print("--- Checking for required tools and files ---")
    if not os.path.exists(KARMADA_KUBECONFIG):
        print_color(
            colors.RED,
            f"FATAL: Karmada kubeconfig not found at '{KARMADA_KUBECONFIG}'.",
        )
        sys.exit(1)
    for member in MEMBER_CLUSTERS:
        config_path = os.path.join(CONFIG_FILES_DIR, f"{member}.config")
        if not os.path.exists(config_path):
            print_color(
                colors.RED,
                f"FATAL: Kubeconfig for '{member}' not found at '{config_path}'.",
            )
            sys.exit(1)
    print_color(colors.GREEN, "All dependencies found.")


from config import (
    MEMBER_CLUSTERS,
    KARMADA_NAMESPACE,
    KARMADA_KUBECONFIG,
    CONFIG_FILES_DIR,
    HOST_KUBECONFIG,
)


def check_control_plane_health():
    """
    Level 1: Verifies all Karmada control plane pods are Running and Ready
    by connecting to the HOST cluster where they are deployed.
    """
    print_color(
        colors.YELLOW, "\n--- Level 1: Checking Karmada Control Plane Health ---"
    )

    
    env = {"KUBECONFIG": HOST_KUBECONFIG}

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
        pod_name, pod_status = pod["metadata"]["name"], pod["status"]["phase"]
        if pod_status != "Running" or not all(
            cs["ready"] for cs in pod["status"].get("containerStatuses", [])
        ):
            print_color(
                colors.RED,
                f"  - Pod '{pod_name}' is not fully ready. Status: {pod_status}",
            )
            all_pods_ready = False
        else:
            print_color(colors.GREEN, f"  - Pod '{pod_name}' is Running and Ready.")

    if all_pods_ready:
        print_color(colors.GREEN, "✅ SUCCESS: All control plane pods are healthy.")

    return all_pods_ready


def check_member_cluster_status():
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
    for member_name in MEMBER_CLUSTERS:
        if member_name not in found_clusters:
            print_color(colors.RED, f"  - Cluster '{member_name}' is not registered.")
            all_clusters_ready = False
            continue
        cluster_item = next(
            item
            for item in clusters_data["items"]
            if item["metadata"]["name"] == member_name
        )
        is_ready = any(
            c.get("type") == "Ready" and c.get("status") == "True"
            for c in cluster_item.get("status", {}).get("conditions", [])
        )
        if is_ready:
            print_color(colors.GREEN, f"  - Cluster '{member_name}' is Ready.")
        else:
            print_color(colors.RED, f"  - Cluster '{member_name}' is not Ready.")
            all_clusters_ready = False
    if all_clusters_ready:
        print_color(
            colors.GREEN, "✅ SUCCESS: All member clusters are registered and ready."
        )
    return all_clusters_ready


def check_e2e_deployment():
    print_color(
        colors.YELLOW, "\n--- Level 3: Performing End-to-End Functionality Test ---"
    )
    karmada_env = {"KUBECONFIG": KARMADA_KUBECONFIG}
    deployment_yaml = """
apiVersion: apps/v1
kind: Deployment
metadata:
  name: karmada-test-nginx
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
      - name: nginx
        image: nginx:1.21.6
"""
    policy_yaml = f"""
apiVersion: policy.karmada.io/v1alpha1
kind: PropagationPolicy
metadata:
  name: nginx-propagation
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

        print("--> Deploying test Nginx application and policy...")
        run_command(["kubectl", "apply", "-f", dep_filename], env=karmada_env)
        run_command(["kubectl", "apply", "-f", pol_filename], env=karmada_env)
        print("--> Waiting up to 90 seconds for resources to propagate...")
        time.sleep(90)
        overall_success = True

        for member in MEMBER_CLUSTERS_TO_DEPLOY:
            print(f"--> Verifying deployment on '{member}'...")
            kubeconfig_path = os.path.join(CONFIG_FILES_DIR, f"{member}.config")
            pods = json.loads(
                run_command(
                    [
                        "kubectl",
                        "--kubeconfig",
                        kubeconfig_path,
                        "get",
                        "pods",
                        "-l",
                        "app=nginx",
                        "-o",
                        "json",
                    ],
                    capture_output=True,
                ).stdout
            ).get("items", [])
            running_pods = [p for p in pods if p["status"]["phase"] == "Running"]
            if len(running_pods) == 2:
                print_color(
                    colors.GREEN, f"  - SUCCESS: Found 2 running pods on '{member}'."
                )
            else:
                print_color(
                    colors.RED,
                    f"  - FAILED: Expected 2 running pods on '{member}', found {len(running_pods)}.",
                )
                overall_success = False

        print(f"--> Verifying deployment is absent from '{MEMBER_CLUSTER_TO_AVOID}'...")
        kubeconfig_path = os.path.join(
            CONFIG_FILES_DIR, f"{MEMBER_CLUSTER_TO_AVOID}.config"
        )
        pods = json.loads(
            run_command(
                [
                    "kubectl",
                    "--kubeconfig",
                    kubeconfig_path,
                    "get",
                    "pods",
                    "-l",
                    "app=nginx",
                    "-o",
                    "json",
                ],
                capture_output=True,
            ).stdout
        ).get("items", [])
        if len(pods) == 0:
            print_color(
                colors.GREEN,
                f"  - SUCCESS: No test pods found on '{MEMBER_CLUSTER_TO_AVOID}', as expected.",
            )
        else:
            print_color(
                colors.RED,
                f"  - FAILED: Found {len(pods)} test pods on '{MEMBER_CLUSTER_TO_AVOID}', expected 0.",
            )
            overall_success = False

        if overall_success:
            print_color(colors.GREEN, "\n✅ SUCCESS: End-to-end test passed.")
        return overall_success
    finally:
        print_color(colors.YELLOW, "\n--- Cleaning up test resources ---")
        if dep_filename:
            run_command(
                ["kubectl", "delete", "-f", dep_filename], env=karmada_env, check=False
            )
        if pol_filename:
            run_command(
                ["kubectl", "delete", "-f", pol_filename], env=karmada_env, check=False
            )


def main():
    check_root_privileges("5-check-karmada.py")
    check_dependencies()
    results = {
        "control_plane": check_control_plane_health(),
        "member_clusters": check_member_cluster_status(),
    }
    if all(results.values()):
        results["e2e_deployment"] = check_e2e_deployment()
    else:
        print_color(
            colors.RED, "\nSkipping Level 3 Test due to failures in preliminary checks."
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
