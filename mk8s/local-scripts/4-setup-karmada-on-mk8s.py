#!/usr/bin/env python3

import subprocess
import sys
import os
import time

# --- Configuration ---
KARMADA_VERSION = "1.14.2"
KUBE_VERSION_TAG = "v1.31.3"  # The K8s version deployed by karmadactl v1.14.2

MEMBER_CLUSTERS = ["member1", "member2", "member3"]
HOST_KUBECONFIG = "/var/snap/microk8s/current/credentials/client.config"
KARMADA_KUBECONFIG = os.path.expanduser("~/.kube/karmada.config")
HOST_REGISTRY = "localhost:32000"

# --- Image Definitions ---
KARMADA_REPO = "docker.io/karmada"
KARMADA_IMAGES = {
    "karmada-aggregated-apiserver": f"{KARMADA_REPO}/karmada-aggregated-apiserver:v{KARMADA_VERSION}",
    "karmada-controller-manager": f"{KARMADA_REPO}/karmada-controller-manager:v{KARMADA_VERSION}",
    "karmada-scheduler": f"{KARMADA_REPO}/karmada-scheduler:v{KARMADA_VERSION}",
    "karmada-webhook": f"{KARMADA_REPO}/karmada-webhook:v{KARMADA_VERSION}",
    "karmada-agent": f"{KARMADA_REPO}/karmada-agent:v{KARMADA_VERSION}",
}

K8S_REPO = "registry.k8s.io"
K8S_IMAGES = {
    "etcd": f"{K8S_REPO}/etcd:3.5.12-0",
    "kube-apiserver": f"{K8S_REPO}/kube-apiserver:{KUBE_VERSION_TAG}",
    "kube-controller-manager": f"{K8S_REPO}/kube-controller-manager:{KUBE_VERSION_TAG}",
}


# --- Helper Function ---

def run_command(command, check=True, env=None):
    """A helper to run a shell command and handle errors."""
    print(f"Executing: {' '.join(command)}")
    try:
        process_env = os.environ.copy()
        if env:
            process_env.update(env)
        # Redirect stdout and stderr to the script's stdout/stderr
        subprocess.run(command, check=check, env=process_env, stdout=sys.stdout, stderr=sys.stderr)
    except subprocess.CalledProcessError as e:
        sys.exit(1)
    except FileNotFoundError:
        print(f"Error: Command '{command[0]}' not found. Is it in your PATH?", file=sys.stderr)
        sys.exit(1)


# --- Step-by-Step Functions ---

def step_1_prepare_host_cluster():
    """
    Step 1: Enables required addons on the MicroK8s host cluster.
    """
    print("--- 1. Preparing the host MicroK8s instance ---")
    print("Enabling DNS, Storage, and local Registry on host...")
    run_command(["microk8s", "enable", "dns", "storage", "registry"])
    run_command(["microk8s", "status", "--wait-ready"])
    print("Host MicroK8s is ready.")


def step_2_push_images_to_local_registry():
    """
    Step 2: Pulls all required container images and pushes them to the local registry.
    """
    print(f"\n--- 2. Pushing all required images to the local registry ({HOST_REGISTRY}) ---")

    all_images = {**KARMADA_IMAGES, **K8S_IMAGES}

    for name, source_image in all_images.items():
        # The local tag will be simpler, e.g., localhost:32000/karmada-webhook:v1.14.2
        target_image = f"{HOST_REGISTRY}/{name}:{source_image.split(':')[-1]}"

        print(f"--> Processing {name}")
        run_command(['docker', 'pull', source_image])
        run_command(['docker', 'tag', source_image, target_image])
        run_command(['docker', 'push', target_image])

    print("All required images pushed to the local registry.")


def step_3_deploy_karmada_control_plane():
    """
    Step 3: Deploys the Karmada control plane using karmadactl init,
    pointing to the images in the local registry.
    """
    print(f"\n--- 3. Deploying Karmada v{KARMADA_VERSION} from local registry ---")

    init_command = [
        "karmadactl", "init",
        "--kubeconfig", HOST_KUBECONFIG,
        "--wait-component-ready-timeout=300",

        # Point each flag to the correct image in our local registry
        "--etcd-image", f"{HOST_REGISTRY}/etcd:3.5.12-0",
        "--karmada-apiserver-image", f"{HOST_REGISTRY}/kube-apiserver:{KUBE_VERSION_TAG}",
        "--karmada-kube-controller-manager-image", f"{HOST_REGISTRY}/kube-controller-manager:{KUBE_VERSION_TAG}",
        "--karmada-aggregated-apiserver-image", f"{HOST_REGISTRY}/karmada-aggregated-apiserver:v{KARMADA_VERSION}",
        "--karmada-controller-manager-image", f"{HOST_REGISTRY}/karmada-controller-manager:v{KARMADA_VERSION}",
        "--karmada-scheduler-image", f"{HOST_REGISTRY}/karmada-scheduler:v{KARMADA_VERSION}",
        "--karmada-webhook-image", f"{HOST_REGISTRY}/karmada-webhook:v{KARMADA_VERSION}",
    ]

    run_command(init_command)
    print("Karmada control plane initialization successful.")
    # A short pause to ensure all components are fully stable before joining clusters.
    time.sleep(15)


def step_4_join_member_clusters():
    """
    Step 4: Joins the pre-existing member clusters to the new Karmada control plane.
    """
    print("\n--- 4. Joining member clusters to the control plane ---")
    agent_image_for_join = f"{HOST_REGISTRY}/karmada-agent:v{KARMADA_VERSION}"

    for member in MEMBER_CLUSTERS:
        # Assuming the config files are in the same directory where this script is run.
        member_config_path = f"/root/{member}.config"
        if not os.path.exists(member_config_path):
            print(f"FATAL ERROR: Kubeconfig for member '{member}' not found at '{member_config_path}'", file=sys.stderr)
            print("       Please run this script from the directory containing the member config files.",
                  file=sys.stderr)
            sys.exit(1)

        print(f"--> Joining cluster: {member}")
        run_command(
            ["karmadactl", "join", member,
             "--cluster-kubeconfig", member_config_path,
             "--karmada-agent-image", agent_image_for_join],
            env={"KUBECONFIG": KARMADA_KUBECONFIG},
        )
    print("All member clusters have been joined.")


# --- Main Execution ---

def main():
    """
    Main function to orchestrate the setup of the Karmada control plane.
    """
    step_1_prepare_host_cluster()
    step_2_push_images_to_local_registry()
    step_3_deploy_karmada_control_plane()
    step_4_join_member_clusters()

    # Final Instructions
    print("\n\n✅ --- Karmada setup on MicroK8s is complete! --- ✅")


if __name__ == "__main__":
    if os.geteuid() != 0:
        print("This script must be run as the 'root' user.", file=sys.stderr)
        sys.exit(1)
    main()
