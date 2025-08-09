#!/usr/bin/env python3

import os
import sys
import subprocess
import shutil


# --- Helper Functions ---


def run_command(command, check=True):
    """A helper to run a shell command and handle errors."""
    print(f"Executing: {' '.join(command)}")
    try:
        subprocess.run(command, check=check)
    except FileNotFoundError:
        print(
            f"Error: Command '{command[0]}' not found. Is it in your PATH?",
            file=sys.stderr,
        )
        sys.exit(1)
    except subprocess.CalledProcessError as e:
        print(f"Error executing command: {' '.join(command)}", file=sys.stderr)
        print(f"Return code: {e.returncode}", file=sys.stderr)
        sys.exit(1)


def command_exists(command):
    """Checks if a command is available in the system's PATH."""
    return shutil.which(command) is not None


# --- Main Installation Logic ---


def install_microk8s():
    """Installs and configures MicroK8s."""
    print("\n--- 1. Setting up MicroK8s ---")
    if command_exists("microk8s"):
        print("MicroK8s is already installed. Skipping installation.")
    else:
        print("Installing MicroK8s...")
        run_command(["snap", "install", "microk8s", "--classic"])

    run_command(["microk8s", "status", "--wait-ready"])


def install_lxd():
    """Installs and configures LXD."""
    print("\n--- 2. Setting up LXD ---")
    if command_exists("lxd"):
        print("LXD is already installed. Skipping installation.")
    else:
        print("Installing LXD...")
        run_command(["snap", "install", "lxd"])

    print("Initializing LXD with default settings...")
    # This command is idempotent and safe to run again.
    run_command(["lxd", "init", "--auto"])


def install_docker():
    """Installs Docker Engine."""
    print("\n--- 3. Setting up Docker ---")
    if command_exists("docker"):
        print("Docker is already installed. Skipping installation.")
        return

    # Check if the system is Debian-based
    if os.path.exists("/etc/debian_version"):
        print("Installing Docker for Debian/Ubuntu...")
        run_command(["apt-get", "update"])
        run_command(["apt-get", "install", "-y", "docker.io"])
    else:
        print(
            "This script cannot automatically install Docker on non-Debian systems.",
            file=sys.stderr,
        )
        print("Please install Docker manually and re-run this script.", file=sys.stderr)
        sys.exit(1)


def install_karmadactl():
    """Installs Karmada's CLI tool, karmadactl."""
    print("\n--- 4. Setting up karmadactl ---")
    if command_exists("karmadactl"):
        print("karmadactl is already installed. Skipping installation.")
        return

    if not command_exists("go"):
        print("Go programming language is not installed.", file=sys.stderr)
        print(
            "Please install Go (e.g., 'apt-get install golang-go') and ensure it's in your PATH.",
            file=sys.stderr,
        )
        sys.exit(1)

    karmada_path = input(
        "Please enter the full path to your Karmada source code directory: "
    ).strip()
    if not os.path.isdir(karmada_path) or not os.path.exists(
        os.path.join(karmada_path, "cmd/karmadactl")
    ):
        print(
            f"Error: Path '{karmada_path}' does not appear to be a valid Karmada source directory.",
            file=sys.stderr,
        )
        sys.exit(1)

    print(f"Changing directory to '{karmada_path}' to install karmadactl...")
    original_dir = os.getcwd()
    os.chdir(karmada_path)

    # Run 'go install' directly as the current user (root).
    run_command(["go", "install", "./cmd/karmadactl"])

    os.chdir(original_dir)
    print("karmadactl installation command executed.")

    # Check if root's GOPATH/bin is in the path and warn if not
    go_bin_path = "/root/go/bin"
    if go_bin_path not in os.environ["PATH"]:
        print(f"\nWARNING: '{go_bin_path}' is not in your PATH.", file=sys.stderr)
        print(
            "You may need to add 'export PATH=$PATH:/root/go/bin' to your /root/.bashrc file and re-login.",
            file=sys.stderr,
        )


def main():
    """Main function to run all prerequisite installations."""
    install_microk8s()
    install_lxd()
    install_docker()
    install_karmadactl()

    print("\n\n✅ --- Prerequisite setup is complete! --- ✅")
    print(
        "You can now proceed with the 'create-member-clusters.py' and 'setup-karmada-on-microk8s.py' scripts."
    )


if __name__ == "__main__":
    # Ensure the script is run as root
    if os.geteuid() != 0:
        print(
            "This script is designed to be run directly by the 'root' user.",
            file=sys.stderr,
        )
        sys.exit(1)
    main()
