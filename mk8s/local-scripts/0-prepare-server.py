#!/usr/bin/env python3

import os
import sys
import subprocess
import shutil
import getpass


# --- Helper Functions ---


def run_command(command, check=True, capture_output=False, text=True):
    """A helper to run a shell command and handle errors."""
    print(f"Executing: {' '.join(command)}")
    try:
        result = subprocess.run(
            command,
            check=check,
            capture_output=capture_output,
            text=text,
        )
        return result
    except FileNotFoundError:
        print(
            f"Error: Command '{command[0]}' not found. Is it in your PATH?",
            file=sys.stderr,
        )
        sys.exit(1)
    except subprocess.CalledProcessError as e:
        print(f"Error executing command: {' '.join(command)}", file=sys.stderr)
        print(f"Return code: {e.returncode}", file=sys.stderr)
        if e.stdout:
            print(f"Stdout:\n{e.stdout}", file=sys.stderr)
        if e.stderr:
            print(f"Stderr:\n{e.stderr}", file=sys.stderr)
        sys.exit(1)


def run_as_user(command):
    """
    Executes a command with the privileges of the user who called sudo.
    This is essential for commands like 'go install'.
    """
    try:
        user_name = os.environ["SUDO_USER"]
        user_uid = int(os.environ["SUDO_UID"])
        user_gid = int(os.environ["SUDO_GID"])
    except KeyError:
        print(
            "This function should be called from a script run with sudo.",
            file=sys.stderr,
        )
        sys.exit(1)

    def demote():
        """Function to be run by preexec_fn to set the user/group ID."""
        os.setgid(user_gid)
        os.setuid(user_uid)

    print(f"Executing as user '{user_name}': {' '.join(command)}")
    # Use preexec_fn to change user before the command is run
    subprocess.run(command, check=True, preexec_fn=demote)


def command_exists(command):
    """Checks if a command is available in the system's PATH."""
    return shutil.which(command) is not None


def add_user_to_group(user, group):
    """Adds a user to a system group idempotently."""
    print(f"Ensuring user '{user}' is in group '{group}'...")
    # The '--quiet' flag ensures it doesn't fail if the user is already a member
    run_command(["sudo", "adduser", "--quiet", user, group])


# --- Main Installation Logic ---


def install_microk8s(user):
    """Installs and configures MicroK8s."""
    print("\n--- 1. Setting up MicroK8s ---")
    if command_exists("microk8s"):
        print("MicroK8s is already installed. Skipping installation.")
    else:
        print("Installing MicroK8s...")
        run_command(["sudo", "snap", "install", "microk8s", "--classic"])

    run_command(["sudo", "microk8s", "status", "--wait-ready"])
    add_user_to_group(user, "microk8s")


def install_lxd(user):
    """Installs and configures LXD."""
    print("\n--- 2. Setting up LXD ---")
    if command_exists("lxd"):
        print("LXD is already installed. Skipping installation.")
    else:
        print("Installing LXD...")
        run_command(["sudo", "snap", "install", "lxd"])

    print("Initializing LXD with default settings...")
    run_command(["sudo", "lxd", "init", "--auto"])
    add_user_to_group(user, "lxd")


def install_docker(user):
    """Installs Docker Engine."""
    print("\n--- 3. Setting up Docker ---")
    if command_exists("docker"):
        print("Docker is already installed. Skipping installation.")
    else:
        # Check if the system is Debian-based
        if os.path.exists("/etc/debian_version"):
            print("Installing Docker for Debian/Ubuntu...")
            run_command(["sudo", "apt-get", "update"])
            run_command(["sudo", "apt-get", "install", "-y", "docker.io"])
        else:
            print(
                "This script cannot automatically install Docker on non-Debian systems.",
                file=sys.stderr,
            )
            print(
                "Please install Docker manually and re-run this script.",
                file=sys.stderr,
            )
            sys.exit(1)

    add_user_to_group(user, "docker")


def install_karmadactl():
    """Installs Karmada's CLI tool, karmadactl."""
    print("\n--- 4. Setting up karmadactl ---")
    if command_exists("karmadactl"):
        print("karmadactl is already installed. Skipping installation.")
        return

    if not command_exists("go"):
        print("Go programming language is not installed.", file=sys.stderr)
        print(
            "Please install Go (https://golang.org/doc/install) and ensure it's in your PATH.",
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

    # Run 'go install' as the original user, not as root
    run_as_user(["go", "install", "./cmd/karmadactl"])

    os.chdir(original_dir)
    print("karmadactl installation command executed.")

    # Check if GOPATH/bin is in the path and warn if not
    go_bin_path = os.path.join(
        os.path.expanduser(f"~{os.environ['SUDO_USER']}"), "go", "bin"
    )
    if go_bin_path not in os.environ["PATH"]:
        print(f"\nWARNING: '{go_bin_path}' is not in your PATH.", file=sys.stderr)
        print(
            "You may need to add 'export PATH=$PATH:$(go env GOPATH)/bin' to your shell profile (.bashrc, .zshrc, etc.).",
            file=sys.stderr,
        )


def main():
    """Main function to run all prerequisite installations."""
    # Get the name of the user who ran sudo
    # try:
    #     current_user = os.environ["SUDO_USER"]
    # except KeyError:
    #     print("This script must be run with sudo.", file=sys.stderr)
    #     sys.exit(1)

    current_user = "root"

    install_microk8s(current_user)
    install_lxd(current_user)
    install_docker(current_user)
    install_karmadactl()

    print("\n\n✅ --- Prerequisite setup is complete! --- ✅")
    print(
        "\nIMPORTANT: For group changes (docker, lxd, microk8s) to take effect, you must"
    )
    print("           LOG OUT and LOG BACK IN to your system before proceeding.")


if __name__ == "__main__":
    print(os.getuid(), os.geteuid())
    if os.getuid() != 0 and os.geteuid() != 0:
        print(
            "This script needs to be run as root or with sudo to install system packages and manage groups.",
            file=sys.stderr,
        )
        print(f"Please run as: sudo python3 {__file__}", file=sys.stderr)
        sys.exit(1)
    main()
