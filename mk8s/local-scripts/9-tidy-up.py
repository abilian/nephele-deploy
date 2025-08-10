#!/usr/bin/env python3

"""Here's what this script does:

1. **Checks for root privileges**: Ensures the script is run with sufficient permissions.
2. **Runs the official deinit command**: Attempts to gracefully deinitialize Karmada using `karmadactl`.
3. **Forcefully deletes the Karmada namespace**: Removes all components in the Karmada namespace.
4. **Finds and deletes all Karmada CRDs**: Cleans up any remaining Custom Resource Definitions related to Karmada.
5. **Destroys member clusters**: Stops and deletes all member clusters defined in the configuration.
6. **Cleans up local kubeconfig files**: Removes any kubeconfig files related to member clusters.
7. **Cleans up the LXD profile**: Deletes the LXD profile used for member clusters.
8. **Disables the host MicroK8s registry**: Cleans up the local registry setup.
"""

import os
import glob

# Import shared configuration and helpers
from common import run_command, check_root_privileges, print_color, colors
from config import (
    MEMBER_CLUSTERS,
    LXD_PROFILE_NAME,
    CONFIG_FILES_DIR,
    KARMADA_NAMESPACE,
    HOST_KUBECONFIG,
)


def main():
    check_root_privileges("6-tidy-up.py")

    print_color(
        colors.YELLOW, "\n--- Starting Hard Cleanup of Karmada Control Plane ---"
    )

    # Step 1: Run the official deinit command (best effort)
    print("--> Attempting graceful deinit with karmadactl...")
    run_command(["karmadactl", "deinit", "--kubeconfig", HOST_KUBECONFIG], check=False)

    # Step 2: Forcefully delete the Karmada namespace to remove all components
    print(f"--> Forcefully deleting namespace '{KARMADA_NAMESPACE}'...")
    run_command(
        [
            "kubectl",
            "--kubeconfig",
            HOST_KUBECONFIG,
            "delete",
            "namespace",
            KARMADA_NAMESPACE,
            "--ignore-not-found=true",
        ]
    )

    # Step 3: Find and delete all Karmada CRDs
    print("--> Finding and deleting all Karmada CRDs...")
    crd_get_cmd = [
        "kubectl",
        "--kubeconfig",
        HOST_KUBECONFIG,
        "get",
        "crds",
        "-o",
        "name",
    ]
    result = run_command(crd_get_cmd, capture_output=True, check=False)
    if result.returncode == 0:
        # Filter for CRDs that belong to Karmada
        karmada_crds = [
            crd for crd in result.stdout.splitlines() if "karmada.io" in crd
        ]
        if karmada_crds:
            print(f"Found {len(karmada_crds)} Karmada CRDs to delete.")
            # Spread the CRDs across a single delete command
            delete_cmd = (
                ["kubectl", "--kubeconfig", HOST_KUBECONFIG, "delete"]
                + karmada_crds
                + ["--ignore-not-found=true"]
            )
            run_command(delete_cmd, check=False)
        else:
            print("No Karmada CRDs found.")

    print_color(colors.GREEN, "✅ Karmada Control Plane cleanup complete.")

    print("\n--- Destroying member clusters ---")
    for member in MEMBER_CLUSTERS:
        print(f"--> Processing {member}")
        run_command(["lxc", "stop", member, "--force"], check=False)
        run_command(["lxc", "delete", member, "--force"], check=False)

    print("\n--- Cleaning up local kubeconfig files ---")
    config_pattern = os.path.join(CONFIG_FILES_DIR, "member*.config")
    for f in glob.glob(config_pattern):
        try:
            os.remove(f)
            print(f"Removed: {f}")
        except OSError as e:
            print_color(colors.RED, f"Error removing file {f}: {e}")

    print(f"\n--- Cleaning up LXD profile '{LXD_PROFILE_NAME}' ---")
    run_command(["lxc", "profile", "delete", LXD_PROFILE_NAME], check=False)

    print("\n--- Disabling host MicroK8s registry ---")
    run_command(["microk8s", "disable", "registry"], check=False)

    print_color(colors.GREEN, "\n✅ --- Full Environment Cleanup is complete. --- ✅")


if __name__ == "__main__":
    main()
