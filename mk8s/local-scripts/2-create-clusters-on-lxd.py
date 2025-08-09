#!/usr/bin/env python3

import subprocess
import sys
import time
import json
import os
import getpass
from grp import getgrnam
from pwd import getpwnam

# --- Configuration ---
MEMBER_CLUSTERS = ["member1", "member2", "member3"]
LXD_PROFILE_NAME = "microk8s"

# NEW: LXD Profile for MicroK8s
# This configuration grants the necessary privileges for MicroK8s to run.
# Source: https://microk8s.io/docs/lxd
LXD_PROFILE_CONFIG = """
config:
  linux.kernel_modules: ip_tables,ip6_tables,nf_nat,overlay,br_netfilter
  raw.lxc: |
    lxc.apparmor.profile = unconfined
    lxc.mount.auto = proc:rw sys:rw
    lxc.cgroup.devices.allow = a
    lxc.cap.drop =
  security.nesting: "true"
  security.privileged: "true"
description: "MicroK8s LXD profile"
devices:
  kmsg:
    path: /dev/kmsg
    source: /dev/kmsg
    type: unix-char
"""


# --- Helper Functions (Unchanged from previous version) ---


def run_command(
    command, capture_output=False, text=True, check=True, command_input=None
):
    """
    A helper to run a shell command and handle errors, with optional input.
    """
    print(f"Executing: {' '.join(command)}")
    try:
        result = subprocess.run(
            command,
            input=command_input,
            capture_output=capture_output,
            text=text,
            check=check,
        )
        return result
    except subprocess.CalledProcessError as e:
        print(f"Error executing command: {' '.join(command)}", file=sys.stderr)
        print(f"Return code: {e.returncode}", file=sys.stderr)
        if e.stdout:
            print(f"Stdout:\n{e.stdout}", file=sys.stderr)
        if e.stderr:
            print(f"Stderr:\n{e.stderr}", file=sys.stderr)
        sys.exit(1)
    except FileNotFoundError:
        print(
            f"Error: Command '{command[0]}' not found. Is it installed and in your PATH?",
            file=sys.stderr,
        )
        sys.exit(1)


def container_exists(name):
    result = subprocess.run(["lxc", "info", name], capture_output=True, text=True)
    return result.returncode == 0


def get_container_ip(name):
    result = run_command(["lxc", "list", name, "--format", "json"], capture_output=True)
    try:
        data = json.loads(result.stdout)
        if not data:
            return None
        addresses = (
            data[0]
            .get("state", {})
            .get("network", {})
            .get("eth0", {})
            .get("addresses", [])
        )
        for addr in addresses:
            if addr.get("family") == "inet":
                return addr.get("address")
    except (json.JSONDecodeError, IndexError, KeyError):
        return None
    return None


def update_kubeconfig_ip(filepath, new_ip):
    with open(filepath, "r") as f:
        content = f.read()
    new_content = content.replace("127.0.0.1", new_ip)
    with open(filepath, "w") as f:
        f.write(new_content)


def set_correct_owner(filepath):
    try:
        user_name = os.environ.get("SUDO_USER", getpass.getuser())
        user_info = getpwnam(user_name)
        uid, gid = user_info.pw_uid, user_info.pw_gid
        os.chown(filepath, uid, gid)
        print(f"Set owner of {filepath} to {user_name}:{getgrnam(gid).gr_name}")
    except Exception as e:
        print(
            f"Warning: Could not change file owner. You may need to run 'sudo chown $USER:$USER {filepath}' manually.",
            file=sys.stderr,
        )
        print(f"Reason: {e}", file=sys.stderr)


# --- Main Logic ---


def setup_lxd_profile():
    """Ensures the required LXD profile for MicroK8s exists."""
    print(f"--- Checking for LXD profile '{LXD_PROFILE_NAME}' ---")
    result = run_command(
        ["lxc", "profile", "list", "--format", "json"], capture_output=True
    )
    profiles = [p["name"] for p in json.loads(result.stdout)]

    if LXD_PROFILE_NAME not in profiles:
        print(f"Profile '{LXD_PROFILE_NAME}' not found. Creating it now...")
        # Pipe the config to the 'lxc profile edit' command to apply it.
        run_command(["lxc", "profile", "create", LXD_PROFILE_NAME])
        run_command(
            ["lxc", "profile", "edit", LXD_PROFILE_NAME],
            command_input=LXD_PROFILE_CONFIG,
        )
        print(f"Successfully created LXD profile '{LXD_PROFILE_NAME}'.")
    else:
        print(f"Profile '{LXD_PROFILE_NAME}' already exists.")


def main():
    """
    Main function to provision MicroK8s clusters in LXD.
    """
    # NEW: Ensure the LXD profile exists before doing anything else.
    setup_lxd_profile()

    print("\n--- Provisioning 3 MicroK8s clusters using LXD ---")

    for member in MEMBER_CLUSTERS:
        print(f"\n>>> Creating cluster: {member}")

        if not container_exists(member):
            print(f"Launching new LXD container for {member} with microk8s profile...")
            # MODIFIED: Apply the profile during launch
            run_command(
                [
                    "lxc",
                    "launch",
                    "ubuntu:22.04",
                    member,
                    "--profile",
                    "default",
                    "--profile",
                    LXD_PROFILE_NAME,
                ]
            )
        else:
            print(
                f"LXD container {member} already exists. Please delete it if it was not created with the '{LXD_PROFILE_NAME}' profile."
            )

        print(f"Waiting for {member} to get a network address...")
        member_ip = None
        while not member_ip:
            member_ip = get_container_ip(member)
            if not member_ip:
                time.sleep(2)
        print(f"Cluster {member} is online at IP: {member_ip}")

        print(f"Waiting for cloud-init to finish in {member}...")
        run_command(["lxc", "exec", member, "--", "cloud-init", "status", "--wait"])

        print(f"Installing MicroK8s in {member}...")
        install_cmd = "if ! command -v microk8s &> /dev/null; then sudo snap install microk8s --classic; fi"
        run_command(["lxc", "exec", member, "--", "/bin/bash", "-c", install_cmd])
        run_command(
            ["lxc", "exec", member, "--", "sudo", "microk8s", "status", "--wait-ready"]
        )

        print(f"Enabling DNS and storage addons in {member}...")
        run_command(
            [
                "lxc",
                "exec",
                member,
                "--",
                "sudo",
                "microk8s",
                "enable",
                "dns",
                "storage",
            ]
        )

        print(f"Extracting kubeconfig for {member}...")
        kubeconfig_path = f"{member}.config"
        kubeconfig_content = run_command(
            ["lxc", "exec", member, "--", "sudo", "microk8s", "config"],
            capture_output=True,
        ).stdout
        with open(kubeconfig_path, "w") as f:
            f.write(kubeconfig_content)

        update_kubeconfig_ip(kubeconfig_path, member_ip)
        set_correct_owner(kubeconfig_path)

        print(
            f">>> Successfully created and configured cluster: {member}. Kubeconfig saved to ./{kubeconfig_path}"
        )

    print("\n--- All member clusters are ready! ---")


if __name__ == "__main__":
    if os.geteuid() != 0:
        print(
            "This script needs to run as root or with sudo to manage LXD profiles and containers.",
            file=sys.stderr,
        )
        print("Please run as: sudo python3 create_member_clusters.py", file=sys.stderr)
        sys.exit(1)
    main()
