#!/usr/bin/env python3

import subprocess
import sys
import os
import time

# --- Configuration ---
HOST_REGISTRY = "localhost:32000"
MEMBER_CLUSTERS = ["member1", "member2", "member3"]
COMPONENTS = [
    "karmada-aggregated-apiserver",
    "karmada-controller-manager",
    "karmada-scheduler",
    "karmada-descheduler",
    "karmada-webhook",
    "karmada-agent",
    "karmada-scheduler-estimator",
    "karmada-interpreter-webhook-example",
    "karmada-search",
    "karmada-operator",
    "karmada-metrics-adapter",
]
# Path to the host's kubeconfig, used by karmadactl
HOST_KUBECONFIG = "/var/snap/microk8s/current/credentials/client.config"
# Path to Karmada's kubeconfig after initialization
KARMADA_KUBECONFIG = os.path.expanduser("~/.kube/karmada.config")


# --- Helper Function ---


def run_command(command, check=True, env=None):
    """A helper to run a shell command and handle errors."""
    print(f"Executing: {' '.join(command)}")
    try:
        # Inherit the environment, but allow overrides
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
            f"Error: Command '{command[0]}' not found. Is it installed and in your PATH?",
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
    print("Enabling DNS, Storage, and local Registry on host...")
    run_command(["microk8s", "enable", "dns", "storage", "registry"])
    run_command(["microk8s", "status", "--wait-ready"])
    print("Host MicroK8s is ready.")

    # 2. Build Karmada Binaries from source
    print("\n--- 2. Building Karmada binaries from source ---")
    for component in COMPONENTS:
        run_command(["make", component, "GOOS=linux"])
    print("All Karmada binaries built successfully.")

    # 3. Build and Push Docker Images to the Local Registry
    print(f"\n--- 3. Building and pushing Docker images to {HOST_REGISTRY} ---")
    for component in COMPONENTS:
        base_image_name = f"docker.io/karmada/{component}:latest"
        local_image_name = f"{HOST_REGISTRY}/karmada/{component}:latest"

        print(f"--> Processing {component}")

        # Build the initial image using the provided Karmada script
        run_command(
            ["hack/docker.sh", component],
            env={
                "VERSION": "latest",
                "REGISTRY": "docker.io/karmada",
                "BUILD_PLATFORMS": "linux/amd64",
            },
        )

        # Re-tag the image for the local MicroK8s registry
        run_command(["docker", "tag", base_image_name, local_image_name])

        # Push the image to the local registry
        run_command(["docker", "push", local_image_name])
    print("All Karmada images pushed to the local registry.")

    # 4. Deploy Karmada Control Plane using karmadactl
    print("\n--- 4. Deploying Karmada control plane on host MicroK8s ---")
    # karmadactl init handles etcd, certs, and control plane component deployment.
    # It needs to be run with sudo to access the host kubeconfig.
    init_command = [
        "sudo",
        "karmadactl",
        "init",
        "--karmada-image-repository",
        f"{HOST_REGISTRY}/karmada",
        "--kubeconfig",
        HOST_KUBECONFIG,
    ]
    run_command(init_command)
    print("Karmada control plane initialization command sent.")

    print("Waiting 60 seconds for control plane components to become ready...")
    time.sleep(60)

    # 5. Join Member Clusters to the Karmada Control Plane
    print("\n--- 5. Joining member clusters to the control plane ---")
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
        # The KUBECONFIG env var tells karmadactl which control plane to talk to.
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
        print(
            "This script needs sudo privileges to enable MicroK8s addons and run 'karmadactl init'.",
            file=sys.stderr,
        )
        print(
            "Please run as: sudo python3 setup-karmada-on-microk8s.py", file=sys.stderr
        )
        sys.exit(1)
    main()
