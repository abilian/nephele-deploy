#!/usr/bin/env python3

"""
Adds a new member cluster to the Karmada federation.

Here's what this script does:
1.  Takes a new cluster name as a command-line argument.
2.  Checks that a cluster with the same name doesn't already exist.
3.  Provisions a new LXD container and installs a complete MicroK8s cluster inside it.
4.  Dynamically assigns a new host port and sets up an LXD proxy for API access.
5.  Generates a new, correctly configured kubeconfig file for the cluster.
6.  Performs a health check to ensure the new cluster is accessible.
7.  Joins the new cluster to the existing Karmada control plane using 'karmadactl join'.
8.  Waits and verifies that the new cluster becomes 'Ready' in the Karmada federation.

Usage:
    sudo ./add-cluster.py <new-cluster-name>
    Example: sudo ./add-cluster.py member4
"""

import sys
import os
import time
import json

# Import shared configuration and helpers
from common import run_command, check_root_privileges, print_color, colors
from config import (
    LXD_PROFILE_NAME,
    CONTAINER_API_PORT,
    CONFIG_FILES_DIR,
    KARMADA_KUBECONFIG,
    PORT_MAPPING,
)


def provision_cluster(cluster_name):
    """Provisions an LXD container and installs MicroK8s inside it."""
    print_color(colors.YELLOW, f"\n--- 1. Provisioning new cluster: {cluster_name} ---")

    # Check if a container with this name already exists
    if run_command(["lxc", "info", cluster_name], check=False).returncode == 0:
        print_color(
            colors.RED,
            f"FATAL: A container named '{cluster_name}' already exists. Aborting.",
        )
        sys.exit(1)

    print(f"--> Launching new LXD container for {cluster_name}...")
    run_command(
        [
            "lxc",
            "launch",
            "ubuntu:22.04",
            cluster_name,
            "--profile",
            "default",
            "--profile",
            LXD_PROFILE_NAME,
        ]
    )

    print(f"--> Waiting for cloud-init to finish in {cluster_name}...")
    run_command(["lxc", "exec", cluster_name, "--", "cloud-init", "status", "--wait"])

    print(f"--> Installing MicroK8s in {cluster_name}...")
    install_cmd = "sudo snap install microk8s --classic"
    run_command(["lxc", "exec", cluster_name, "--", "/bin/bash", "-c", install_cmd])
    run_command(
        [
            "lxc",
            "exec",
            cluster_name,
            "--",
            "sudo",
            "microk8s",
            "status",
            "--wait-ready",
        ]
    )

    print(f"--> Enabling required addons (dns, hostpath-storage)...")
    run_command(
        ["lxc", "exec", cluster_name, "--", "sudo", "microk8s", "enable", "dns"]
    )
    run_command(
        [
            "lxc",
            "exec",
            cluster_name,
            "--",
            "sudo",
            "microk8s",
            "enable",
            "hostpath-storage",
        ]
    )

    print_color(colors.GREEN, f"✅ Cluster '{cluster_name}' provisioned successfully.")


def setup_api_access(cluster_name):
    """Sets up LXD port forwarding and generates the modified kubeconfig file."""
    print_color(colors.YELLOW, f"\n--- 2. Setting up API access for {cluster_name} ---")

    # Dynamically find the next available port
    highest_port = max(int(p) for p in PORT_MAPPING.values())
    new_host_port = highest_port + 1

    print(f"--> Assigning new host port {new_host_port} for the API proxy.")

    proxy_device_name = "proxy-k8s"
    run_command(
        [
            "lxc",
            "config",
            "device",
            "add",
            cluster_name,
            proxy_device_name,
            "proxy",
            f"listen=tcp:0.0.0.0:{new_host_port}",
            f"connect=tcp:127.0.0.1:{CONTAINER_API_PORT}",
        ]
    )

    print(f"--> Extracting and modifying kubeconfig for {cluster_name}...")
    kubeconfig_path = os.path.join(CONFIG_FILES_DIR, f"{cluster_name}.config")
    result = run_command(
        ["lxc", "exec", cluster_name, "--", "sudo", "microk8s", "config"],
        capture_output=True,
    )

    modified_content = result.stdout.replace(
        f"server: https://127.0.0.1:{CONTAINER_API_PORT}",
        f"server: https://127.0.0.1:{new_host_port}",
    )
    with open(kubeconfig_path, "w") as f:
        f.write(modified_content)

    print_color(colors.GREEN, f"✅ Kubeconfig saved to '{kubeconfig_path}'.")
    return kubeconfig_path


def health_check_cluster(cluster_name, kubeconfig_path):
    """Performs a health check to ensure the cluster is accessible via the proxy."""
    print_color(
        colors.YELLOW, f"\n--- 3. Health checking new cluster: {cluster_name} ---"
    )
    for i in range(12):  # Try for 2 minutes
        result = run_command(
            ["kubectl", "--kubeconfig", kubeconfig_path, "get", "nodes"], check=False
        )
        if result.returncode == 0:
            print_color(colors.GREEN, f"✅ Health check PASSED for {cluster_name}.")
            return True
        print_color(
            colors.YELLOW, f"Health check attempt {i + 1}/12 failed. Retrying in 10s..."
        )
        time.sleep(10)

    print_color(colors.RED, f"❌ FATAL: Health check FAILED for {cluster_name}.")
    sys.exit(1)


def join_to_karmada(cluster_name, kubeconfig_path):
    """Joins the new cluster to the Karmada control plane."""
    print_color(
        colors.YELLOW,
        f"\n--- 4. Joining '{cluster_name}' to the Karmada control plane ---",
    )

    join_command = [
        "karmadactl",
        "join",
        cluster_name,
        "--cluster-kubeconfig",
        kubeconfig_path,
    ]
    # The KUBECONFIG env var tells karmadactl where to find the control plane
    run_command(join_command, env={"KUBECONFIG": KARMADA_KUBECONFIG})
    print_color(colors.GREEN, f"✅ Join command executed for '{cluster_name}'.")


def verify_karmada_join(cluster_name):
    """Waits for the new cluster to report a 'Ready' status in Karmada."""
    print_color(
        colors.YELLOW, f"\n--- 5. Verifying '{cluster_name}' is Ready in Karmada ---"
    )

    for i in range(18):  # Wait up to 3 minutes
        check_cmd = [
            "kubectl",
            "--kubeconfig",
            KARMADA_KUBECONFIG,
            "get",
            "cluster",
            cluster_name,
            "-o",
            "jsonpath={.status.conditions[?(@.type=='Ready')].status}",
        ]
        result = run_command(check_cmd, check=False, capture_output=True)

        if result.returncode == 0 and result.stdout.strip() == "True":
            print_color(
                colors.GREEN,
                f"✅ Verification PASSED: Cluster '{cluster_name}' is now Ready in Karmada.",
            )
            return True

        print(f"Cluster not ready yet. Retrying in 10s...")
        time.sleep(10)

    print_color(
        colors.RED,
        f"❌ FATAL: Timed out waiting for cluster '{cluster_name}' to become Ready.",
    )
    sys.exit(1)


def main():
    """Main execution function."""
    check_root_privileges("add-cluster.py")

    # --- Argument Parsing ---
    if len(sys.argv) != 2:
        print(f"Usage: {sys.argv[0]} <new-cluster-name>")
        print("Example: sudo ./add-cluster.py member4")
        sys.exit(1)
    cluster_name = sys.argv[1]

    # --- Orchestration ---
    provision_cluster(cluster_name)
    kubeconfig_path = setup_api_access(cluster_name)
    health_check_cluster(cluster_name, kubeconfig_path)
    join_to_karmada(cluster_name, kubeconfig_path)
    verify_karmada_join(cluster_name)

    print_color(
        colors.GREEN, "\n\n========================================================"
    )
    print_color(
        colors.GREEN,
        f"✅ Success! New cluster '{cluster_name}' has been added and joined to the Karmada federation.",
    )
    print_color(
        colors.YELLOW,
        f"You can check the status with: kubectl --kubeconfig {KARMADA_KUBECONFIG} get clusters",
    )
    print_color(
        colors.GREEN, "========================================================"
    )


if __name__ == "__main__":
    main()
