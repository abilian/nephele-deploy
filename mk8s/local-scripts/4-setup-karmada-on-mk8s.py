#!/usr/bin/env python3

import subprocess
import sys
import os
import time
import tempfile

# --- Configuration ---
KARMADA_VERSION = "1.14.2"
KUBE_VERSION_TAG = "v1.31.3"

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

def run_command(command, check=True, env=None, capture_output=False):
    """A helper to run a shell command and handle errors."""
    print(f"Executing: {' '.join(command)}")
    try:
        process_env = os.environ.copy()
        if env:
            process_env.update(env)
        result = subprocess.run(
            command, check=check, env=process_env,
            stdout=sys.stdout if not capture_output else subprocess.PIPE,
            stderr=sys.stderr if not capture_output else subprocess.PIPE,
            text=True
        )
        return result
    except subprocess.CalledProcessError as e:
        sys.exit(1)
    except FileNotFoundError:
        print(f"Error: Command '{command[0]}' not found. Is it in your PATH?", file=sys.stderr)
        sys.exit(1)


# --- Step-by-Step Functions ---

def step_1_prepare_host_cluster():
    """Step 1: Enables required addons on the MicroK8s host cluster."""
    print("--- 1. Preparing the host MicroK8s instance ---")
    run_command(["microk8s", "enable", "dns", "storage", "registry"])
    run_command(["microk8s", "status", "--wait-ready"])
    print("Host MicroK8s is ready.")


def step_2_push_images_to_local_registry():
    """Step 2: Pulls all container images and pushes them to the local registry."""
    print(f"\n--- 2. Pushing all required images to the local registry ({HOST_REGISTRY}) ---")
    all_images = {**KARMADA_IMAGES, **K8S_IMAGES}
    for name, source_image in all_images.items():
        # Push to a simple, predictable path in the local registry
        target_image = f"{HOST_REGISTRY}/{name}:{source_image.split(':')[-1]}"
        print(f"--> Processing {name}")
        run_command(['docker', 'pull', source_image])
        run_command(['docker', 'tag', source_image, target_image])
        run_command(['docker', 'push', target_image])
    print("All required images pushed to the local registry.")


def step_3_deploy_karmada_control_plane():
    """Step 3: Deploys the Karmada control plane using karmadactl init."""
    print(f"\n--- 3. Deploying Karmada v{KARMADA_VERSION} from local registry ---")
    init_command = [
        "karmadactl", "init",
        "--kubeconfig", HOST_KUBECONFIG,
        "--wait-component-ready-timeout=300",
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
    print("Waiting 15s for the Karmada controller to be ready...")
    time.sleep(15)


def step_4_join_member_clusters():
    """
    Step 4: Joins the member clusters using the correct two-step manual process.
    """
    print("\n--- 4. Joining member clusters to the control plane ---")

    for member in MEMBER_CLUSTERS:
        print(f"--> Joining cluster: {member}")
        member_config_path = f"/root/{member}.config"
        if not os.path.exists(member_config_path):
            print(f"FATAL ERROR: Kubeconfig for member '{member}' not found at '{member_config_path}'", file=sys.stderr)
            sys.exit(1)

        # Step 4.1: Use 'karmadactl join' to simply create the Cluster object.
        # This command has no invalid image flags and will succeed.
        print(f"    - Registering cluster object for '{member}'...")
        join_command = [
            "karmadactl", "join", member,
            "--cluster-kubeconfig", member_config_path,
        ]
        run_command(join_command, env={"KUBECONFIG": KARMADA_KUBECONFIG})

        # Step 4.2: Use 'karmadactl agent' to generate the agent's YAML manifest.
        print(f"    - Generating and applying karmada-agent manifest for '{member}'...")
        agent_image_for_join = f"{HOST_REGISTRY}/karmada-agent:v{KARMADA_VERSION}"

        agent_yaml_command = [
            "karmadactl", "agent",
            "--karmada-kubeconfig", KARMADA_KUBECONFIG,
            "--cluster-name", member,
            # This command correctly accepts the custom image flag
            "--karmada-agent-image", agent_image_for_join,
        ]

        # Capture the generated YAML output.
        result = run_command(agent_yaml_command, capture_output=True)
        agent_yaml_content = result.stdout

        # Apply the generated manifest to the *member* cluster.
        with tempfile.NamedTemporaryFile(mode='w', delete=True, suffix=".yaml") as tmp_file:
            tmp_file.write(agent_yaml_content)
            tmp_file.flush()  # Ensure content is written to disk

            apply_command = ["kubectl", "apply", "-f", tmp_file.name]
            # Use the member cluster's kubeconfig to apply the manifest.
            run_command(apply_command, env={"KUBECONFIG": member_config_path})

    print("All member clusters have been joined.")


# --- Main Execution ---

def main():
    """Orchestrates the setup of the Karmada control plane."""
    step_1_prepare_host_cluster()
    step_2_push_images_to_local_registry()
    step_3_deploy_karmada_control_plane()
    step_4_join_member_clusters()

    print("\n\n✅ --- Karmada setup on MicroK8s is complete! --- ✅")


if __name__ == "__main__":
    if os.geteuid() != 0:
        print("This script must be run as the 'root' user.", file=sys.stderr)
        sys.exit(1)
    main()
