#!/usr/bin/env python3

"""Here's what this script does:

1. **Checks for root privileges**: Ensures the script is run with sufficient permissions.
2. **Ensures the LXD profile for MicroK8s exists**: Creates or updates the LXD profile with necessary configurations.
3. **Provisions LXD containers for each member cluster**: Launches new containers or re-uses existing ones.
4. **Installs MicroK8s and enables addons**: Installs MicroK8s in each container and enables necessary addons like DNS and storage.
5. **Sets up port forwarding**: Configures LXD to forward ports from the host to the container for API access.
6. **Generates kubeconfig files**: Modifies the kubeconfig files to point to the correct API server addresses.
7. **Performs health checks**: Ensures each cluster is accessible and ready by checking the API server connection.
"""

import json
import os
import sys
import time
from pwd import getpwnam

# Import shared configuration and helpers
from common import run_command, check_root_privileges, print_color, colors
from config import (
    MEMBER_CLUSTERS,
    LXD_PROFILE_NAME,
    PORT_MAPPING,
    CONTAINER_API_PORT,
    CONFIG_FILES_DIR,
)

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


def setup_lxd_profile():
    """Ensures the required LXD profile for MicroK8s exists."""
    print(f"--- Checking for LXD profile '{LXD_PROFILE_NAME}' ---")
    result = run_command(
        ["lxc", "profile", "list", "--format", "json"], capture_output=True
    )
    profiles = [p["name"] for p in json.loads(result.stdout)]
    if LXD_PROFILE_NAME not in profiles:
        print(f"Profile '{LXD_PROFILE_NAME}' not found. Creating it now...")
        run_command(["lxc", "profile", "create", LXD_PROFILE_NAME])
        run_command(
            ["lxc", "profile", "edit", LXD_PROFILE_NAME],
            command_input=LXD_PROFILE_CONFIG,
        )
    else:
        print(f"Profile '{LXD_PROFILE_NAME}' already exists.")


def provision_container(member_name):
    """Launches or re-uses an LXD container with the correct profile."""
    print_color(colors.YELLOW, f"\n>>> Processing container: {member_name}")
    if not run_command(["lxc", "info", member_name], check=False).returncode == 0:
        print(f"Launching new LXD container for {member_name}...")
        run_command(
            [
                "lxc",
                "launch",
                "ubuntu:22.04",
                member_name,
                "--profile",
                "default",
                "--profile",
                LXD_PROFILE_NAME,
            ]
        )
    else:
        print(f"Container '{member_name}' already exists. Re-using.")


def install_microk8s_in_container(member_name):
    """Installs and enables addons for MicroK8s inside a container."""
    print(f"Waiting for cloud-init to finish in {member_name}...")
    run_command(["lxc", "exec", member_name, "--", "cloud-init", "status", "--wait"])

    print(f"Installing MicroK8s in {member_name}...")
    install_cmd = 'if ! command -v microk8s &> /dev/null; then sudo snap install microk8s --classic; else echo "MicroK8s already installed."; fi'
    run_command(["lxc", "exec", member_name, "--", "/bin/bash", "-c", install_cmd])
    run_command(
        ["lxc", "exec", member_name, "--", "sudo", "microk8s", "status", "--wait-ready"]
    )

    print(f"Enabling addons in {member_name}...")
    run_command(["lxc", "exec", member_name, "--", "sudo", "microk8s", "enable", "dns"])
    run_command(
        [
            "lxc",
            "exec",
            member_name,
            "--",
            "sudo",
            "microk8s",
            "enable",
            "hostpath-storage",
        ]
    )


def setup_port_forward_and_kubeconfig(member_name):
    """Sets up LXD port forwarding and generates the modified kubeconfig file."""
    host_port = PORT_MAPPING[member_name]
    proxy_device_name = "proxy-k8s"
    print(
        f"Setting up port forward: localhost:{host_port} -> container:{CONTAINER_API_PORT} for {member_name}..."
    )

    run_command(
        ["lxc", "config", "device", "remove", member_name, proxy_device_name],
        check=False,
    )
    proxy_command = [
        "lxc",
        "config",
        "device",
        "add",
        member_name,
        proxy_device_name,
        "proxy",
        f"listen=tcp:0.0.0.0:{host_port}",
        f"connect=tcp:127.0.0.1:{CONTAINER_API_PORT}",
    ]
    run_command(proxy_command)

    print(f"Extracting and modifying kubeconfig for {member_name}...")
    kubeconfig_path = os.path.join(CONFIG_FILES_DIR, f"{member_name}.config")
    result = run_command(
        ["lxc", "exec", member_name, "--", "sudo", "microk8s", "config"],
        capture_output=True,
    )

    modified_content = result.stdout.replace(
        f"server: https://127.0.0.1:{CONTAINER_API_PORT}",
        f"server: https://127.0.0.1:{host_port}",
    )
    with open(kubeconfig_path, "w") as f:
        f.write(modified_content)

    user_name = os.environ.get("SUDO_USER", "root")
    user_info = getpwnam(user_name)
    os.chown(kubeconfig_path, user_info.pw_uid, user_info.pw_gid)

    return kubeconfig_path


def health_check_cluster(member_name, kubeconfig_path):
    """Performs a health check to ensure the cluster is accessible."""
    print(f"--> Health checking connection to {member_name} via port forward...")
    for i in range(12):  # Try for 2 minutes
        check_cmd = [
            "kubectl",
            "--kubeconfig",
            kubeconfig_path,
            "get",
            "nodes",
            "--insecure-skip-tls-verify",
        ]
        result = run_command(check_cmd, check=False)
        if result.returncode == 0:
            print_color(colors.GREEN, f"✅ Health check PASSED for {member_name}.")
            return True
        print_color(
            colors.YELLOW, f"Health check attempt {i + 1}/12 failed. Retrying in 10s..."
        )
        time.sleep(10)

    print_color(
        colors.RED,
        f"❌ Health check FAILED for {member_name}. The API server is not reachable via the port forward.",
    )
    return False


def main():
    """Orchestrates the provisioning of all member clusters."""
    check_root_privileges("1-create-clusters-on-lxd.py")
    setup_lxd_profile()

    print("\n--- Provisioning 3 MicroK8s clusters using LXD ---")
    for member in MEMBER_CLUSTERS:
        provision_container(member)
        install_microk8s_in_container(member)
        kubeconfig_path = setup_port_forward_and_kubeconfig(member)

        if not health_check_cluster(member, kubeconfig_path):
            sys.exit(1)  # Exit if a cluster fails its health check

        print_color(
            colors.GREEN, f">>> Successfully processed and verified cluster: {member}."
        )

    print_color(colors.GREEN, "\n--- All member clusters are ready! ---")


if __name__ == "__main__":
    main()
