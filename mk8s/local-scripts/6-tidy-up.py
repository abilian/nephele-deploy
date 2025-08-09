#!/usr/bin/env python3

import subprocess
import sys
import os
import glob

# --- Configuration ---
MEMBER_CLUSTERS = ["member1", "member2", "member3"]
LXD_PROFILE_NAME = "microk8s"


# --- Helper Function ---


def run_command(command, check=True):
    """
    A helper to run a shell command and handle errors.
    If 'check' is False, it will not raise an exception for a non-zero exit code.
    """
    print(f"Executing: {' '.join(command)}")
    try:
        subprocess.run(command, check=check)
    except FileNotFoundError:
        # This error is critical, as it means a required tool is not installed.
        print(
            f"Error: Command '{command[0]}' not found. Is it installed and in your PATH?",
            file=sys.stderr,
        )
        sys.exit(1)
    # CalledProcessError is not caught here if check=False


# --- Main Logic ---


def main():
    """
    Main function to clean up the Karmada multi-cluster environment.
    """
    print("--- Destroying member clusters ---")
    for member in MEMBER_CLUSTERS:
        print(f"--> Processing {member}")
        # Stop the container. We use check=False to ignore errors if it's already stopped or doesn't exist.
        run_command(["lxc", "stop", member, "--force"], check=False)
        # Delete the container. check=False ignores errors if it doesn't exist.
        run_command(["lxc", "delete", member], check=False)

    print("\n--- Cleaning up local kubeconfig files ---")
    # Use glob to find all files matching the pattern 'member*.config'
    config_files = glob.glob("member*.config")
    if not config_files:
        print("No kubeconfig files found to clean up.")
    else:
        for f in config_files:
            try:
                os.remove(f)
                print(f"Removed: {f}")
            except OSError as e:
                print(f"Error removing file {f}: {e}", file=sys.stderr)

    print(f"\n--- Cleaning up LXD profile '{LXD_PROFILE_NAME}' ---")
    # Attempt to delete the profile; ignore errors if it's in use or doesn't exist.
    run_command(["lxc", "profile", "delete", LXD_PROFILE_NAME], check=False)

    print("\n--- Disabling host MicroK8s registry ---")
    # This might fail if the registry is already disabled, so we don't check the exit code.
    run_command(["microk8s", "disable", "registry"], check=False)

    print("\n✅ --- Cleanup complete. --- ✅")


if __name__ == "__main__":
    if os.geteuid() != 0:
        print(
            "This script needs sudo privileges to manage LXD containers.",
            file=sys.stderr,
        )
        print("Please run as: sudo python3 tidy-up.py", file=sys.stderr)
        sys.exit(1)
    main()
