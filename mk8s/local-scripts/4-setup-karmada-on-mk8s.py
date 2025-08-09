#!/usr/bin/env python3

import subprocess
import sys
import os
import time

# --- Configuration ---
KARMADA_VERSION = "1.14.2"
MEMBER_CLUSTERS = ["member1", "member2", "member3"]
HOST_KUBECONFIG = "/var/snap/microk8s/current/credentials/client.config"
KARMADA_KUBECONFIG = os.path.expanduser("~/.kube/karmada.config")
IMAGE_REPO = "docker.io/karmada"


# --- Helper Function ---


def run_command(command, check=True, env=None):
    """A helper to run a shell command and handle errors."""
    print(f"Executing: {' '.join(command)}")
    try:
        process_env = os.environ.copy()
        if env:
            process_env.update(env)
        subprocess.run(command, check=check, env=process_env)
    except subprocess.CalledProcessError as e:
        print(f"Error executing command: {' '.join(command)}", file=sys.stderr)
        print(f"Return code: {e.returncode}", file=sys.stderr)
        sys.exit(1)
    except FileNotFoundError:
        print(
            f"Error: Command '{command[0]}' not found. Is it in your PATH?",
            file=sys.stderr,
        )
        sys.exit(1)


# --- Main Logic ---


def main():
    """
    Main function to set up Karmada control plane on a MicroK8s host.
    """
    # 1. Prepare Host MicroK8s
    print("--- 1. Preparing the host MicroK8s instance ---")
    print("Enabling DNS and Storage on host...")
    run_command(["microk8s", "enable", "dns", "storage"])
    run_command(["microk8s", "status", "--wait-ready"])
    print("Host MicroK8s is ready.")

    # 2. Deploy Karmada Control Plane using karmadactl
    print(
        f"\n--- 2. Deploying Karmada v{KARMADA_VERSION} control plane on host MicroK8s ---"
    )

    init_command = [
        "karmadactl",
        "init",
        "--kubeconfig",
        HOST_KUBECONFIG,
        # Increase the timeout to 5 minutes (300 seconds) to allow for slower image pulls and pod startup
        "--wait-component-ready-timeout=300",
        # Specify images for all core control plane components
        "--etcd-image",
        f"registry.k8s.io/etcd:3.5.12-0",
        "--karmada-apiserver-image",
        f"{IMAGE_REPO}/karmada-apiserver:{KARMADA_VERSION}",
        "--karmada-aggregated-apiserver-image",
        f"{IMAGE_REPO}/karmada-aggregated-apiserver:{KARMADA_VERSION}",
        "--karmada-controller-manager-image",
        f"{IMAGE_REPO}/karmada-controller-manager:{KARMADA_VERSION}",
        "--karmada-scheduler-image",
        f"{IMAGE_REPO}/karmada-scheduler:{KARMADA_VERSION}",
        "--karmada-webhook-image",
        f"{IMAGE_REPO}/karmada-webhook:{KARMADA_VERSION}",
    ]

    run_command(init_command)
    print("Karmada control plane initialization successful.")

    # A short, explicit wait after the command reports success can still be helpful.
    print("Waiting 15 seconds for all components to stabilize...")
    time.sleep(15)

    # 3. Join Member Clusters to the Karmada Control Plane
    print("\n--- 3. Joining member clusters to the control plane ---")
    for member in MEMBER_CLUSTERS:
        member_config_path = f"./{member}.config"
        if not os.path.exists(member_config_path):
            print(
                f"FATAL ERROR: Kubeconfig for {member} not found at '{member_config_path}'",
                file=sys.stderr,
            )
            print(
                "Please run the 'create-member-clusters.py' script first.",
                file=sys.stderr,
            )
            sys.exit(1)

        print(f"--> Joining cluster: {member}")
        run_command(
            ["karmadactl", "join", member, "--cluster-kubeconfig", member_config_path],
            env={"KUBECONFIG": KARMADA_KUBECONFIG},
        )
    print("All member clusters have been joined.")

    # Final Instructions
    print("\n\n✅ --- Karmada setup on MicroK8s is complete! --- ✅")
    print("\nTo interact with the Karmada control plane, run:")
    print(f"  export KUBECONFIG={KARMADA_KUBECONFIG}")
    print("\nYou can check the cluster status with:")
    print("  kubectl get clusters")
    print("\nTo interact with a member cluster directly (for example, member1), run:")
    print("  kubectl --kubeconfig ./member1.config get nodes")


if __name__ == "__main__":
    if os.geteuid() != 0:
        print("This script must be run as the 'root' user.", file=sys.stderr)
        sys.exit(1)
    main()
