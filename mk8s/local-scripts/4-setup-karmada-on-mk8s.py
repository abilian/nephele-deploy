#!/usr/bin/env python3

import subprocess
import sys
import os
import time

# --- (Configuration and Helper functions are unchanged) ---
KARMADA_VERSION = "1.14.2"
KUBE_VERSION_TAG = "v1.31.3"
MEMBER_CLUSTERS = ["member1", "member2", "member3"]
HOST_KUBECONFIG = "/var/snap/microk8s/current/credentials/client.config"
KARMADA_KUBECONFIG = os.path.expanduser("~/.kube/karmada.config")
HOST_REGISTRY = "localhost:32000"
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


def run_command(command, check=True, env=None, capture_output=False):
    """A helper to run a shell command and handle errors."""
    print(f"Executing: {' '.join(command)}")
    try:
        process_env = os.environ.copy()
        if env: process_env.update(env)
        result = subprocess.run(
            command, check=check, env=process_env,
            stdout=sys.stdout if not capture_output else subprocess.PIPE,
            stderr=sys.stderr if not capture_output else subprocess.PIPE,
            text=True
        )
        return result
    except subprocess.CalledProcessError as e:
        if check: sys.exit(1)
        return e
    except FileNotFoundError:
        print(f"Error: Command '{command[0]}' not found.", file=sys.stderr)
        sys.exit(1)


# --- (step_1 and step_2 are unchanged) ---
def step_1_prepare_host_cluster():
    print("--- 1. Preparing the host MicroK8s instance ---")
    run_command(["microk8s", "enable", "dns", "storage", "registry"])
    run_command(["microk8s", "status", "--wait-ready"])
    print("Host MicroK8s is ready.")


def step_2_push_images_to_local_registry():
    print(f"\n--- 2. Pushing all required images to the local registry ({HOST_REGISTRY}) ---")
    all_images = {**KARMADA_IMAGES, **K8S_IMAGES}
    for name, source_image in all_images.items():
        target_image = f"{HOST_REGISTRY}/{name}:{source_image.split(':')[-1]}"
        print(f"--> Processing {name}")
        run_command(['docker', 'pull', source_image])
        run_command(['docker', 'tag', source_image, target_image])
        run_command(['docker', 'push', target_image])
    print("All required images pushed to the local registry.")


def step_3_deploy_and_wait_for_karmada_control_plane():
    """
    Step 3: Deploys the Karmada control plane and then waits intelligently
    for its APIs to become available.
    """
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

    # NEW: Robust wait logic using the purpose-built 'karmadactl' command.
    print("\nWaiting for the Karmada control plane API to become fully available...")
    max_wait_seconds = 120
    start_time = time.time()
    api_ready = False
    while time.time() - start_time < max_wait_seconds:
        # 'karmadactl get clusters' is the most reliable check. It will fail if the
        # 'clusters.cluster.karmada.io' CRD is not yet ready.
        check_api_cmd = ["karmadactl", "get", "clusters"]

        # We use check=False because we expect this command to fail initially.
        result = run_command(check_api_cmd, check=False, env={"KUBECONFIG": KARMADA_KUBECONFIG}, capture_output=True)

        # A successful command (return code 0) means the API is ready.
        if result.returncode == 0:
            print("Karmada control plane API is now available!")
            api_ready = True
            break

        print("API not ready yet, waiting 10 seconds...")
        time.sleep(10)

    if not api_ready:
        print("FATAL: Timed out waiting for Karmada APIs to become available.", file=sys.stderr)
        # Provide final debugging instructions
        print("Please run 'kubectl get pods -n karmada-system' and 'kubectl logs <pod> -n karmada-system' to debug.",
              file=sys.stderr)
        sys.exit(1)


# --- (step_4 is unchanged) ---
def step_4_join_member_clusters():
    print("\n--- 4. Joining member clusters to the control plane ---")
    for member in MEMBER_CLUSTERS:
        print(f"--> Joining cluster: {member}")
        member_config_path = f"/root/{member}.config"
        if not os.path.exists(member_config_path):
            print(f"FATAL ERROR: Kubeconfig for member '{member}' not found at '{member_config_path}'", file=sys.stderr)
            sys.exit(1)
        join_command = [
            "karmadactl", "join", member,
            "--cluster-kubeconfig", member_config_path,
        ]
        run_command(join_command, env={"KUBECONFIG": KARMADA_KUBECONFIG})
    print("All member clusters have been joined.")


# --- MODIFIED MAIN FUNCTION ---
def main():
    """Orchestrates the setup of the Karmada control plane."""
    step_1_prepare_host_cluster()
    step_2_push_images_to_local_registry()
    step_3_deploy_and_wait_for_karmada_control_plane()  # Use the new function name
    step_4_join_member_clusters()

    print("\n\n✅ --- Karmada setup on MicroK8s is complete! --- ✅")


if __name__ == "__main__":
    if os.geteuid() != 0:
        print("This script must be run as the 'root' user.", file=sys.stderr)
        sys.exit(1)
    main()
