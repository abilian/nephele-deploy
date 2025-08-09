#!/usr/bin/env python3

import os
import sys
import subprocess
import shutil
import urllib.request

# The desired version of Karmada tools to install is now hardcoded here.
KARMADA_VERSION = "1.14.2"

# --- Helper Functions ---


def run_command(command, check=True, command_input=None, env=None):
    """
    A helper to run a shell command and handle errors, with optional input and environment variables.
    """
    display_command = " ".join(command)
    if command_input:
        display_command += " <<< [INPUT]"
    print(f"Executing: {display_command}")

    try:
        process_env = os.environ.copy()
        if env:
            process_env.update(env)

        subprocess.run(
            command, input=command_input, check=check, text=True, env=process_env
        )
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
        print("MicroK8s is already installed. Skipping.")
    else:
        print("Installing MicroK8s...")
        run_command(["snap", "install", "microk8s", "--classic"])
    run_command(["microk8s", "status", "--wait-ready"])


def install_lxd():
    """Installs and configures LXD."""
    print("\n--- 2. Setting up LXD ---")
    if command_exists("lxd"):
        print("LXD is already installed. Skipping.")
    else:
        print("Installing LXD...")
        run_command(["snap", "install", "lxd"])
    print("Initializing LXD with default settings...")
    run_command(["lxd", "init", "--auto"])


def install_docker():
    """Installs Docker Engine."""
    print("\n--- 3. Setting up Docker ---")
    if command_exists("docker"):
        print("Docker is already installed. Skipping.")
        return
    if os.path.exists("/etc/debian_version"):
        print("Installing Docker for Debian/Ubuntu...")
        run_command(["apt-get", "update"])
        run_command(["apt-get", "install", "-y", "docker.io"])
    else:
        print(
            "Cannot automatically install Docker on non-Debian systems. Please install manually.",
            file=sys.stderr,
        )
        sys.exit(1)


def install_kubectl():
    """Installs the kubectl command-line tool."""
    print("\n--- 4. Setting up kubectl ---")
    if command_exists("kubectl"):
        print("kubectl is already installed. Skipping.")
    else:
        print("Installing kubectl via snap...")
        run_command(["snap", "install", "kubectl", "--classic"])


def install_karmada_tools():
    """Installs Karmada CLI tools for a specific version using the official one-click install script."""
    print(f"\n--- 5. Setting up Karmada CLI Tools (Version: {KARMADA_VERSION}) ---")

    if not command_exists("curl"):
        print(
            "Error: 'curl' is required to download the installation script.",
            file=sys.stderr,
        )
        print(
            "Please install it (e.g., 'apt-get install curl') and re-run.",
            file=sys.stderr,
        )
        sys.exit(1)

    # Set the environment variable for the installation script to use the hardcoded version.
    install_env = {"INSTALL_CLI_VERSION": KARMADA_VERSION}

    # Fetch the installation script from the master branch.
    script_url = "https://raw.githubusercontent.com/karmada-io/karmada/master/hack/install-cli.sh"
    try:
        print(f"Downloading installation script from {script_url}...")
        with urllib.request.urlopen(script_url) as response:
            install_script_content = response.read().decode("utf-8")
    except Exception as e:
        print(f"Failed to download installation script: {e}", file=sys.stderr)
        sys.exit(1)

    tools_to_install = {
        "karmadactl": ["bash"],
        "kubectl-karmada": ["bash", "-s", "kubectl-karmada"],
    }

    for tool, command in tools_to_install.items():
        if command_exists(tool):
            print(f"{tool} is already installed. Skipping.")
        else:
            print(f"--> Installing {tool} v{KARMADA_VERSION}...")
            run_command(command, command_input=install_script_content, env=install_env)


def main():
    """Main function to run all prerequisite installations."""
    install_microk8s()
    install_lxd()
    install_docker()
    install_kubectl()
    install_karmada_tools()

    print("\n\n✅ --- Prerequisite setup is complete! --- ✅")
    print(
        "You can now proceed with the 'create-member-clusters.py' "
        "and 'setup-karmada-on-microk8s.py' scripts."
    )


if __name__ == "__main__":
    if os.geteuid() != 0:
        print(
            "This script must be run as the 'root' user or with sudo.", file=sys.stderr
        )
        sys.exit(1)
    main()
