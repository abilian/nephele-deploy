#!/usr/bin/env python3

import urllib.request
import json
import time
import os
import sys

from common import (
    run_command,
    command_exists,
    check_root_privileges,
    print_color,
    colors,
)
from config import KARMADA_VERSION, LXD_BRIDGE_NAME


def wait_for_lxd_daemon():
    """Waits for the LXD daemon to be ready by polling it."""
    print("--> Waiting for LXD daemon to become responsive...")
    for i in range(12):  # Wait up to 2 minutes
        result = run_command(["lxc", "list"], check=False)
        if result.returncode == 0:
            print_color(colors.GREEN, "LXD daemon is ready.")
            return
        time.sleep(10)
    print_color(colors.RED, "FATAL: Timed out waiting for LXD daemon.")
    sys.exit(1)


def install_microk8s():
    print("\n--- 1. Setting up MicroK8s ---")
    if not command_exists("microk8s"):
        print("Installing MicroK8s...")
        run_command(["snap", "install", "microk8s", "--classic"])
    else:
        print("MicroK8s is already installed. Skipping.")
    run_command(["microk8s", "status", "--wait-ready"])


def install_lxd_and_configure_network():
    """Installs LXD and configures its network, handling systemd reloads."""
    print("\n--- 2. Setting up LXD and Host Networking ---")
    if not command_exists("lxd"):
        print("Installing LXD...")
        run_command(["snap", "install", "lxd"])
        wait_for_lxd_daemon()
    else:
        print("LXD is already installed. Skipping installation.")

    run_command(["lxd", "init", "--auto"])
    wait_for_lxd_daemon()

    print(f"Configuring LXD network bridge '{LXD_BRIDGE_NAME}'...")
    run_command(["lxc", "network", "set", LXD_BRIDGE_NAME, "ipv4.address=auto"])
    run_command(["lxc", "network", "set", LXD_BRIDGE_NAME, "ipv4.nat=true"])

    print("Reloading systemd daemon configuration...")
    run_command(["systemctl", "daemon-reload"])

    print("Restarting LXD daemon to apply configuration...")
    run_command(["systemctl", "restart", "snap.lxd.daemon.service"])
    time.sleep(10)


def install_docker():
    print("\n--- 3. Setting up Docker ---")
    if command_exists("docker"):
        print("Docker is already installed. Skipping.")
        return
    if os.path.exists("/etc/debian_version"):
        print("Installing Docker for Debian/Ubuntu...")
        run_command(["apt-get", "update"])
        run_command(["apt-get", "install", "-y", "docker.io"])
    else:
        print_color(
            colors.RED, "Cannot automatically install Docker on non-Debian systems."
        )
        sys.exit(1)


def install_kubectl():
    print("\n--- 4. Setting up kubectl ---")
    if not command_exists("kubectl"):
        print("Installing kubectl via snap...")
        run_command(["snap", "install", "kubectl", "--classic"])
    else:
        print("kubectl is already installed. Skipping.")


def install_karmada_tools():
    print(f"\n--- 5. Setting up Karmada CLI Tools (Version: {KARMADA_VERSION}) ---")
    if not command_exists("curl"):
        print_color(colors.RED, "Error: 'curl' is required.")
        sys.exit(1)
    install_env = {"INSTALL_CLI_VERSION": KARMADA_VERSION}
    script_url = "https://raw.githubusercontent.com/karmada-io/karmada/master/hack/install-cli.sh"
    try:
        with urllib.request.urlopen(script_url) as response:
            install_script_content = response.read().decode("utf-8")
    except Exception as e:
        print_color(colors.RED, f"Failed to download installation script: {e}")
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


def step_6_verify_and_repair_network_setup():
    print(f"\n--- 6. Verifying and Repairing Network Setup for '{LXD_BRIDGE_NAME}' ---")
    print(f"--> Forcibly bringing interface '{LXD_BRIDGE_NAME}' UP...")
    run_command(["ip", "link", "set", LXD_BRIDGE_NAME, "up"])
    time.sleep(2)
    print(f"--> Checking and ensuring required firewall rules exist...")
    rules_to_check = {
        "FORWARD_IN": [
            "iptables",
            "-C",
            "FORWARD",
            "-i",
            LXD_BRIDGE_NAME,
            "-j",
            "ACCEPT",
        ],
        "FORWARD_OUT": [
            "iptables",
            "-C",
            "FORWARD",
            "-o",
            LXD_BRIDGE_NAME,
            "-j",
            "ACCEPT",
        ],
        "INPUT": ["iptables", "-C", "INPUT", "-i", LXD_BRIDGE_NAME, "-j", "ACCEPT"],
    }
    for name, check_cmd in rules_to_check.items():
        if run_command(check_cmd, check=False).returncode != 0:
            print(f"Firewall rule ({name}) missing. Adding it now...")
            add_cmd = check_cmd.copy()
            add_cmd[1] = "-A"
            run_command(add_cmd)
    print("\n--> Final verification of network state:")
    all_checks_passed = True
    try:
        result = run_command(
            ["ip", "-j", "addr", "show", LXD_BRIDGE_NAME], capture_output=True
        )
        data = json.loads(result.stdout)
        if data and "UP" in data[0].get("flags", []):
            print(
                f"✅ Verification PASSED: LXD bridge '{LXD_BRIDGE_NAME}' is administratively UP."
            )
        else:
            print(
                f"❌ Verification FAILED: LXD bridge '{LXD_BRIDGE_NAME}' is not administratively UP."
            )
            all_checks_passed = False
        if "local" in data[0].get("addr_info", [{}])[0]:
            print(f"✅ Verification PASSED: Host has an IP address on the bridge.")
        else:
            print(
                f"❌ Verification FAILED: Host does not have an IP address on the bridge."
            )
            all_checks_passed = False
    except (json.JSONDecodeError, IndexError):
        all_checks_passed = False
    if all(
        run_command(cmd, check=False).returncode == 0 for cmd in rules_to_check.values()
    ):
        print(f"✅ Verification PASSED: All required iptables rules are set.")
    else:
        print(
            f"❌ Verification FAILED: One or more required iptables rules are missing."
        )
        all_checks_passed = False
    return all_checks_passed


def main():
    check_root_privileges("0-prepare-server.py")
    install_microk8s()
    install_lxd_and_configure_network()
    install_docker()
    install_kubectl()
    install_karmada_tools()
    if step_6_verify_and_repair_network_setup():
        print_color(
            colors.GREEN,
            "\n\n✅ --- Prerequisite and Network setup is complete and verified! --- ✅",
        )
    else:
        print_color(
            colors.RED,
            "\n\n❌ --- Prerequisite setup complete, but network verification failed! --- ❌",
        )
        sys.exit(1)


if __name__ == "__main__":
    main()
