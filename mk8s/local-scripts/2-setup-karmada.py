#!/usr/bin/env python3

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
    Step 4: Joins member clusters, ensuring a consistent and ready state for all.
    """
    print("\n--- 4. Joining member clusters to the control plane ---")
    for member in MEMBER_CLUSTERS:
        print_color(colors.YELLOW, f"--> Processing cluster: {member}")

        # Check the status of the cluster.
        check_join_cmd = ["karmadactl", "get", "cluster", member, "-o", "json"]
        result = run_command(
            check_join_cmd,
            check=False,
            env={"KUBECONFIG": KARMADA_KUBECONFIG},
            capture_output=True,
        )

        cluster_exists = result.returncode == 0
        cluster_ready = False
        if cluster_exists:
            try:
                cluster_info = json.loads(result.stdout)
                for condition in cluster_info.get("status", {}).get("conditions", []):
                    if (
                        condition.get("type") == "Ready"
                        and condition.get("status") == "True"
                    ):
                        cluster_ready = True
                        break
            except (json.JSONDecodeError, KeyError):
                pass

        # If the cluster exists but is not ready, unjoin it first to ensure a clean state.
        if cluster_exists and not cluster_ready:
            print_color(
                colors.YELLOW,
                f"Cluster '{member}' exists but is not Ready. Unjoining to reset...",
            )
            unjoin_cmd = ["karmadactl", "unjoin", member]
            run_command(unjoin_cmd, env={"KUBECONFIG": KARMADA_KUBECONFIG})
            cluster_exists = False  # Mark for re-joining

        if cluster_exists and cluster_ready:
            print_color(
                colors.GREEN,
                f"Cluster '{member}' is already registered and Ready. Skipping join.",
            )
            continue

        member_config_path = os.path.join(CONFIG_FILES_DIR, f"{member}.config")

        print(f"    - Registering cluster object for '{member}'...")
        join_command = [
            "karmadactl",
            "join",
            member,
            "--cluster-kubeconfig",
            member_config_path,
        ]
        run_command(join_command, env={"KUBECONFIG": KARMADA_KUBECONFIG})

        print(f"    - Creating bootstrap token for agent deployment...")

        token_create_cmd = ["karmadactl", "token", "create", "--print-register-command"]
        result = run_command(
            token_create_cmd,
            env={"KUBECONFIG": KARMADA_KUBECONFIG},
            capture_output=True,
        )
        register_command_str = result.stdout.strip()

        print(f"    - Deploying karmada-agent to '{member}'...")
        register_command_list = register_command_str.split()
        register_command_list.extend(
            [
                # We must explicitly name the cluster we are registering the agent for.
                "--cluster-name",
                member,
                "--cluster-kubeconfig",
                member_config_path,
                "--private-image-registry",
                HOST_REGISTRY,
            ]
        )

        run_command(register_command_list)

    print("All member clusters have been joined and configured.")


def main():
    check_root_privileges("4-setup-karmada-on-mk8s.py")
    run_preflight_checks()
    step_1_prepare_host_cluster()
    step_2_push_images_to_local_registry()
    step_3_deploy_and_wait_for_karmada_control_plane()
    step_4_join_member_clusters()

    print_color(
        colors.GREEN, "\n\n✅ --- Karmada setup on MicroK8s is complete! --- ✅"
    )


if __name__ == "__main__":
    main()
