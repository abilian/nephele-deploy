#!/usr/bin/env python3

"""
Destroys a member cluster and removes it from the Karmada federation.

Here's what this script does:
1.  Takes a cluster name as a command-line argument.
2.  Checks that the cluster exists in both Karmada and LXD.
3.  Unjoins the cluster from the Karmada control plane using 'karmadactl unjoin'.
    This removes the Cluster object and the karmada-agent from the member.
4.  Stops and deletes the LXD container associated with the cluster.
5.  Deletes the local kubeconfig file for the cluster.

Usage:
    sudo ./destroy-cluster.py <cluster-name>
    Example: sudo ./destroy-cluster.py member4
"""

import sys
import os

# Import shared configuration and helpers
from common import run_command, check_root_privileges, print_color, colors
from config import (
    CONFIG_FILES_DIR,
    KARMADA_KUBECONFIG,
)


def pre_flight_checks(cluster_name):
    """Verifies that the target cluster exists before proceeding."""
    print_color(
        colors.YELLOW, f"\n--- 1. Running pre-flight checks for '{cluster_name}' ---"
    )
    all_ok = True

    # Check if the cluster is registered in Karmada
    check_karmada_cmd = [
        "kubectl",
        "--kubeconfig",
        KARMADA_KUBECONFIG,
        "get",
        "cluster",
        cluster_name,
    ]
    if run_command(check_karmada_cmd, check=False).returncode != 0:
        print_color(
            colors.RED, f"Error: Cluster '{cluster_name}' is not registered in Karmada."
        )
        all_ok = False

    # Check if the LXD container exists
    if run_command(["lxc", "info", cluster_name], check=False).returncode != 0:
        print_color(
            colors.RED, f"Error: LXD container '{cluster_name}' does not exist."
        )
        all_ok = False

    if not all_ok:
        print_color(colors.RED, "\nFATAL: Pre-flight checks failed. Aborting.")
        sys.exit(1)

    print_color(colors.GREEN, "✅ Pre-flight checks passed.")


def unjoin_from_karmada(cluster_name):
    """Unjoins the cluster from the Karmada control plane."""
    print_color(
        colors.YELLOW,
        f"\n--- 2. Unjoining '{cluster_name}' from the Karmada control plane ---",
    )

    # The KUBECONFIG env var tells karmadactl where to find the control plane
    unjoin_command = ["karmadactl", "unjoin", cluster_name]
    run_command(unjoin_command, env={"KUBECONFIG": KARMADA_KUBECONFIG})

    print_color(
        colors.GREEN, f"✅ Cluster '{cluster_name}' has been unjoined from Karmada."
    )


def destroy_lxd_container(cluster_name):
    """Stops and deletes the LXD container."""
    print_color(
        colors.YELLOW, f"\n--- 3. Destroying LXD container '{cluster_name}' ---"
    )

    print(f"--> Forcefully stopping container '{cluster_name}'...")
    run_command(["lxc", "stop", cluster_name, "--force"], check=False)

    print(f"--> Deleting container '{cluster_name}'...")
    run_command(["lxc", "delete", cluster_name, "--force"], check=False)

    print_color(colors.GREEN, f"✅ LXD container '{cluster_name}' has been destroyed.")


def cleanup_local_files(cluster_name):
    """Removes the local kubeconfig file for the cluster."""
    print_color(
        colors.YELLOW, f"\n--- 4. Cleaning up local files for '{cluster_name}' ---"
    )

    kubeconfig_path = os.path.join(CONFIG_FILES_DIR, f"{cluster_name}.config")

    if os.path.exists(kubeconfig_path):
        try:
            os.remove(kubeconfig_path)
            print_color(colors.GREEN, f"✅ Removed kubeconfig file: {kubeconfig_path}")
        except OSError as e:
            print_color(colors.RED, f"Error removing file {kubeconfig_path}: {e}")
    else:
        print_color(
            colors.YELLOW,
            f"Info: Kubeconfig file not found at {kubeconfig_path}, skipping.",
        )


def main():
    """Main execution function."""
    check_root_privileges("destroy-cluster.py")

    # --- Argument Parsing ---
    if len(sys.argv) != 2:
        print(f"Usage: {sys.argv[0]} <cluster-name>")
        print("Example: sudo ./destroy-cluster.py member4")
        sys.exit(1)
    cluster_name = sys.argv[1]

    # --- Orchestration ---
    pre_flight_checks(cluster_name)
    unjoin_from_karmada(cluster_name)
    destroy_lxd_container(cluster_name)
    cleanup_local_files(cluster_name)

    print_color(
        colors.GREEN, "\n\n========================================================"
    )
    print_color(
        colors.GREEN,
        f"✅ Success! Cluster '{cluster_name}' has been completely destroyed.",
    )
    print_color(
        colors.YELLOW,
        f"You can verify with: kubectl --kubeconfig {KARMADA_KUBECONFIG} get clusters",
    )
    print_color(
        colors.GREEN, "========================================================"
    )


if __name__ == "__main__":
    main()
