#!/usr/bin/env python3

import os
import sys
import time
import tempfile

# Import shared configuration and helpers
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


def step_1_prepare_host_cluster():
    print("--- 1. Preparing the host MicroK8s instance ---")
    run_command(["microk8s", "enable", "dns", "storage", "registry"])
    run_command(["microk8s", "status", "--wait-ready"])
    print("Host MicroK8s is ready.")


def step_2_push_images_to_local_registry():
    print(
        f"\n--- 2. Pushing all required images to the local registry ({HOST_REGISTRY}) ---"
    )
    all_images = {**KARMADA_IMAGES, **K8S_IMAGES}
    for name, source_image in all_images.items():
        target_image = f"{HOST_REGISTRY}/{name}:{source_image.split(':')[-1]}"
        print(f"--> Processing {name}")
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
    max_wait_seconds = 120
    start_time = time.time()
    api_ready = False
    while time.time() - start_time < max_wait_seconds:
        check_api_cmd = ["karmadactl", "get", "clusters"]
        result = run_command(
            check_api_cmd,
            check=False,
            env={"KUBECONFIG": KARMADA_KUBECONFIG},
            capture_output=True,
        )
        if result.returncode == 0:
            print_color(colors.GREEN, "Karmada control plane API is now available!")
            api_ready = True
            break
        time.sleep(10)

    if not api_ready:
        print_color(
            colors.RED, "FATAL: Timed out waiting for Karmada APIs to become available."
        )
        sys.exit(1)


def step_4_join_member_clusters():
    print("\n--- 4. Joining member clusters to the control plane ---")
    for member in MEMBER_CLUSTERS:
        print_color(colors.YELLOW, f"--> Joining cluster: {member}")
        member_config_path = os.path.join(CONFIG_FILES_DIR, f"{member}.config")
        if not os.path.exists(member_config_path):
            print_color(
                colors.RED,
                f"FATAL ERROR: Kubeconfig for member '{member}' not found at '{member_config_path}'",
            )
            sys.exit(1)

        print(f"    - Registering cluster object for '{member}'...")
        join_command = [
            "karmadactl",
            "join",
            member,
            "--cluster-kubeconfig",
            member_config_path,
        ]
        run_command(join_command, env={"KUBECONFIG": KARMADA_KUBECONFIG})

        print(f"    - Generating and applying karmada-agent manifest for '{member}'...")
        agent_image_for_join = f"{HOST_REGISTRY}/karmada-agent:v{KARMADA_VERSION}"
        agent_yaml_command = [
            "karmadactl",
            "agent",
            "--karmada-kubeconfig",
            KARMADA_KUBECONFIG,
            "--cluster-name",
            member,
            "--karmada-agent-image",
            agent_image_for_join,
        ]
        result = run_command(agent_yaml_command, capture_output=True)

        with tempfile.NamedTemporaryFile(
            mode="w", delete=True, suffix=".yaml"
        ) as tmp_file:
            tmp_file.write(result.stdout)
            tmp_file.flush()
            apply_command = ["kubectl", "apply", "-f", tmp_file.name]
            run_command(apply_command, env={"KUBECONFIG": member_config_path})

    print("All member clusters have been joined.")


def main():
    check_root_privileges("4-setup-karmada-on-mk8s.py")
    step_1_prepare_host_cluster()
    step_2_push_images_to_local_registry()
    step_3_deploy_and_wait_for_karmada_control_plane()
    step_4_join_member_clusters()

    print_color(
        colors.GREEN, "\n\n✅ --- Karmada setup on MicroK8s is complete! --- ✅"
    )


if __name__ == "__main__":
    main()
