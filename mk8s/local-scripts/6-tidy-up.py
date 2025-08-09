#!/usr/bin/env python3

import os
import glob

# Import shared configuration and helpers
from common import run_command, check_root_privileges, print_color, colors
from config import MEMBER_CLUSTERS, LXD_PROFILE_NAME, CONFIG_FILES_DIR


def main():
    check_root_privileges("6-tidy-up.py")

    print("--- Destroying member clusters ---")
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

    print_color(colors.GREEN, "\n✅ --- Cleanup complete. --- ✅")


if __name__ == "__main__":
    main()
