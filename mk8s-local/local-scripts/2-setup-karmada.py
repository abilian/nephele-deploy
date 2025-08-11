#!/usr/bin/env python3

"""Here's what this script does:

1. **Runs pre-flight checks**: Ensures all required kubeconfigs for member clusters are present.
2. **Prepares the host MicroK8s instance**: Enables necessary addons like DNS, storage, and registry.
3. **Pushes required images to the local registry**: Pulls images from remote sources and pushes them to the local MicroK8s registry.
4. **Deploys Karmada control plane**: Initializes Karmada using the local registry images.
5. **Waits for Karmada API to become available**: Ensures the Karmada control plane is fully operational.
6. **Joins member clusters**: Registers each member cluster with the Karmada control plane, ensuring they are ready and healthy.
"""

import json
import os
import sys
import time

from common import run_command, check_root_privileges, print_color, colors
from config import (
    MEMBER_CLUSTERS,
    KARMADA_VERSION,
    KUBE_VERSION_TAG,
    HOST_KUBECONFIG,
    KARMADA_KUBECONFIG,
    HOST_REGISTRY,
    KARMADA_IMAGES,
    K8S_IMAGES,
    CONFIG_FILES_DIR,
)


def main():
    check_root_privileges("4-setup-karmada-on-mk8s.py")
    run_preflight_checks()
    step_1_prepare_host_cluster()
    # Added because the registry can take a while to become available (seemingly)
    time.sleep(10)
    step_2_push_images_to_local_registry()
    step_3_deploy_and_wait_for_karmada_control_plane()
    step_4_join_member_clusters()

    print_color(
        colors.GREEN, "\n\n✅ --- Karmada setup on MicroK8s is complete! --- ✅"
    )


def run_preflight_checks():
    """Checks for potential issues before starting the installation to fail early."""
    print_color(colors.YELLOW, "\n--- Running Pre-flight Checks ---")
    all_ok = True
    for member in MEMBER_CLUSTERS:
        member_config_path = os.path.join(CONFIG_FILES_DIR, f"{member}.config")
        if not os.path.exists(member_config_path):
            print_color(
                colors.RED,
                f"❌ Prerequisite FAILED: Kubeconfig for member '{member}' not found at '{member_config_path}'",
            )
            all_ok = False

    if not all_ok:
        print_color(
            colors.RED,
            "\nFATAL: Pre-flight checks failed. Please resolve the issues above.",
        )
        sys.exit(1)

    print_color(colors.GREEN, "✅ Pre-flight checks passed.")


def wait_for_registry():
    print_color(
        colors.YELLOW,
        "\n--> Waiting for the local container registry to become available...",
    )
    max_wait_seconds = 180
    start_time = time.time()
    while time.time() - start_time < max_wait_seconds:
        cmd = [
            "microk8s",
            "kubectl",
            "get",
            "deployment",
            "registry",
            "-n",
            "container-registry",
            "-o",
            "json",
        ]
        result = run_command(cmd, check=False, capture_output=True)
        if result.returncode == 0:
            try:
                deployment = json.loads(result.stdout)
                if deployment.get("status", {}).get("availableReplicas", 0) >= 1:
                    print_color(colors.GREEN, "✅ Local container registry is ready.")
                    time.sleep(5)
                    return
            except (json.JSONDecodeError, KeyError):
                pass
        print("Registry not ready yet, waiting 15 seconds...")
        time.sleep(15)
    print_color(
        colors.RED,
        "FATAL: Timed out waiting for the local registry to become available.",
    )
    sys.exit(1)


def step_1_prepare_host_cluster():
    print("--- 1. Preparing the host MicroK8s instance ---")
    run_command(["microk8s", "enable", "dns"])
    run_command(["microk8s", "enable", "hostpath-storage"])
    run_command(["microk8s", "enable", "registry"])
    run_command(["microk8s", "status", "--wait-ready"])
    wait_for_registry()
    print("Host MicroK8s is ready.")


def step_2_push_images_to_local_registry():
    print(
        f"\n--- 2. Pushing all required images to the local registry ({HOST_REGISTRY}) ---"
    )
    all_images = {**KARMADA_IMAGES, **K8S_IMAGES}
    for name, source_image in all_images.items():
        target_image = f"{HOST_REGISTRY}/{name}:{source_image.split(':')[-1]}"
        run_command(["docker", "pull", source_image])
        run_command(["docker", "tag", source_image, target_image])
        run_command(["docker", "push", target_image])
    print("All required images pushed to the local registry.")


def step_3_deploy_and_wait_for_karmada_control_plane():
    print(f"\n--- 3. Deploying Karmada v{KARMADA_VERSION} from local registry ---")
    init_command = [
        "karmadactl",
        "init",
        "--kubeconfig",
        HOST_KUBECONFIG,
        "--wait-component-ready-timeout=300",
        "--etcd-image",
        f"{HOST_REGISTRY}/etcd:3.5.12-0",
        "--karmada-apiserver-image",
        f"{HOST_REGISTRY}/kube-apiserver:{KUBE_VERSION_TAG}",
        "--karmada-kube-controller-manager-image",
        f"{HOST_REGISTRY}/kube-controller-manager:{KUBE_VERSION_TAG}",
        "--karmada-aggregated-apiserver-image",
        f"{HOST_REGISTRY}/karmada-aggregated-apiserver:v{KARMADA_VERSION}",
        "--karmada-controller-manager-image",
        f"{HOST_REGISTRY}/karmada-controller-manager:v{KARMADA_VERSION}",
        "--karmada-scheduler-image",
        f"{HOST_REGISTRY}/karmada-scheduler:v{KARMADA_VERSION}",
        "--karmada-webhook-image",
        f"{HOST_REGISTRY}/karmada-webhook:v{KARMADA_VERSION}",
    ]
    run_command(init_command)
    print("Karmada control plane initialization successful.")

    print("\nWaiting for the Karmada control plane API to become fully available...")
    max_wait_seconds = 180
    start_time = time.time()
    api_ready = False
    while time.time() - start_time < max_wait_seconds:
        check_api_cmd = ["kubectl", "api-resources", "--api-group=cluster.karmada.io"]
        result = run_command(
            check_api_cmd,
            check=False,
            env={"KUBECONFIG": KARMADA_KUBECONFIG},
            capture_output=True,
        )
        if result.returncode == 0 and "clusters" in result.stdout:
            print_color(colors.GREEN, "Karmada 'clusters' API is now available!")
            api_ready = True
            break
        time.sleep(10)
    if not api_ready:
        print_color(
            colors.RED, "FATAL: Timed out waiting for Karmada APIs to become available."
        )
        sys.exit(1)


def step_4_join_member_clusters():
    """
    Step 4: Joins member clusters if they are not already registered,
    then waits for all of them to be ready.
    """
    print("\n--- 4. Joining member clusters to the control plane ---")

    # First, join any clusters that are not already present and ready.
    for member in MEMBER_CLUSTERS:
        if not is_cluster_registered_and_ready(member):
            join_cluster(member)

    wait_for_all_clusters_ready()

    print("All member clusters have been joined and verified.")


def is_cluster_registered_and_ready(member_name):
    """
    Checks if a cluster is registered with Karmada and in a Ready state.
    Returns True if ready, False otherwise.
    """

    print(f"--> Checking status of cluster '{member_name}'...")
    check_cmd = ["karmadactl", "get", "cluster", member_name, "-o", "json"]
    result = run_command(
        check_cmd,
        check=False,
        env={"KUBECONFIG": KARMADA_KUBECONFIG},
        capture_output=True,
    )

    if result.returncode != 0:
        print(f"Cluster '{member_name}' is not registered.")
        return False

    try:
        cluster_info = json.loads(result.stdout)
        for condition in cluster_info.get("status", {}).get("conditions", []):
            if condition.get("type") == "Ready" and condition.get("status") == "True":
                print_color(
                    colors.GREEN,
                    f"Cluster '{member_name}' is already registered and Ready.",
                )
                return True
    except (json.JSONDecodeError, KeyError):
        pass  # If JSON is invalid, it's not ready

    print_color(colors.YELLOW, f"Cluster '{member_name}' exists but is not yet Ready.")
    return False


def join_cluster(member_name):
    """
    Joins a single member cluster to the Karmada control plane using Push mode.
    """
    print_color(colors.YELLOW, f"--> Joining cluster: {member_name}")
    member_config_path = os.path.join(CONFIG_FILES_DIR, f"{member_name}.config")

    join_command = [
        "karmadactl",
        "join",
        member_name,
        "--cluster-kubeconfig",
        member_config_path,
        # # This flag is still crucial to tell the agent where to pull its image from.
        # "--private-image-registry", HOST_REGISTRY
    ]
    run_command(join_command, env={"KUBECONFIG": KARMADA_KUBECONFIG})


def wait_for_all_clusters_ready(timeout_seconds=60):
    """
    Waits for all member clusters to report a Ready status.
    Exits with an error if the timeout is reached.
    """
    print_color(
        colors.YELLOW,
        f"\n--> Waiting up to {timeout_seconds} seconds for all clusters to become Ready...",
    )
    start_time = time.time()
    while time.time() - start_time < timeout_seconds:
        ready_clusters = [
            member
            for member in MEMBER_CLUSTERS
            if is_cluster_registered_and_ready(member)
        ]

        if len(ready_clusters) == len(MEMBER_CLUSTERS):
            print_color(colors.GREEN, "\n✅ All member clusters are now Ready.")
            return

        print(
            f"Waiting... ({len(ready_clusters)}/{len(MEMBER_CLUSTERS)} clusters ready). Retrying in 10 seconds."
        )
        time.sleep(10)

    print_color(
        colors.RED, "\nFATAL: Timed out waiting for all clusters to become Ready."
    )
    print_color(colors.YELLOW, "Use 'kubectl get clusters' to see the current status.")
    print_color(
        colors.YELLOW,
        "To debug a non-ready cluster, check the 'karmada-agent' pod logs in its 'karmada-system' namespace.",
    )
    sys.exit(1)


if __name__ == "__main__":
    main()
