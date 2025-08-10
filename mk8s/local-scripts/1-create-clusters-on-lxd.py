#!/usr/bin/env python3

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


def container_exists(name):
    return run_command(["lxc", "info", name], check=False).returncode == 0


def set_correct_owner(filepath):
    user_name = os.environ.get("SUDO_USER", "root")
    user_info = getpwnam(user_name)
    os.chown(filepath, user_info.pw_uid, user_info.pw_gid)


def setup_lxd_profile():
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


def main():
    check_root_privileges("2-create-clusters-on-lxd.py")
    setup_lxd_profile()

    print("\n--- Provisioning 3 MicroK8s clusters using LXD ---")
    for member in MEMBER_CLUSTERS:
        print_color(colors.YELLOW, f"\n>>> Processing cluster: {member}")
        if not container_exists(member):
            print(f"Launching new LXD container for {member}...")
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
            print(f"Container '{member}' already exists. Re-using.")

        print(f"Waiting for cloud-init to finish in {member}...")
        run_command(["lxc", "exec", member, "--", "cloud-init", "status", "--wait"])

        print(f"Installing MicroK8s in {member}...")
        install_cmd = 'if ! command -v microk8s &> /dev/null; then sudo snap install microk8s --classic; else echo "MicroK8s already installed."; fi'
        run_command(["lxc", "exec", member, "--", "/bin/bash", "-c", install_cmd])
        run_command(
            ["lxc", "exec", member, "--", "sudo", "microk8s", "status", "--wait-ready"]
        )

        
        print(f"Enabling addons in {member}...")
        run_command(["lxc", "exec", member, "--", "sudo", "microk8s", "enable", "dns"])
        run_command(
            [
                "lxc",
                "exec",
                member,
                "--",
                "sudo",
                "microk8s",
                "enable",
                "hostpath-storage",
            ]
        )

        # Robustly add the port-forwarding proxy device
        host_port = PORT_MAPPING[member]
        proxy_device_name = "proxy-k8s"
        print(
            f"Setting up port forward: localhost:{host_port} -> container:{CONTAINER_API_PORT} for {member}..."
        )
        run_command(
            ["lxc", "config", "device", "remove", member, proxy_device_name],
            check=False,
        )
        proxy_command = [
            "lxc",
            "config",
            "device",
            "add",
            member,
            proxy_device_name,
            "proxy",
            f"listen=tcp:0.0.0.0:{host_port}",
            f"connect=tcp:127.0.0.1:{CONTAINER_API_PORT}",
        ]
        run_command(proxy_command)

        print(f"Extracting and modifying kubeconfig for {member}...")
        kubeconfig_path = os.path.join(CONFIG_FILES_DIR, f"{member}.config")
        result = run_command(
            ["lxc", "exec", member, "--", "sudo", "microk8s", "config"],
            capture_output=True,
        )
        modified_content = result.stdout.replace(
            f"server: https://127.0.0.1:{CONTAINER_API_PORT}",
            f"server: https://127.0.0.1:{host_port}",
        )
        with open(kubeconfig_path, "w") as f:
            f.write(modified_content)
        set_correct_owner(kubeconfig_path)

        # Health check to verify connectivity
        print(f"--> Health checking connection to {member} via port forward...")
        health_check_ok = False
        for i in range(10):  # Try for 100 seconds
            
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
                print_color(colors.GREEN, f"✅ Health check PASSED for {member}.")
                health_check_ok = True
                break
            print_color(
                colors.YELLOW,
                f"Health check attempt {i + 1}/10 failed. Retrying in 10s...",
            )
            time.sleep(10)

        if not health_check_ok:
            print_color(
                colors.RED,
                f"❌ Health check FAILED for {member}. The API server is not reachable via the port forward.",
            )
            sys.exit(1)

        print_color(
            colors.GREEN, f">>> Successfully processed and verified cluster: {member}."
        )

    print_color(colors.GREEN, "\n--- All member clusters are ready! ---")


if __name__ == "__main__":
    main()
