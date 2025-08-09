#!/usr/bin/env python3

import os
import sys
import subprocess
import shutil
import urllib.request
import json
import time

# --- Configuration ---
KARMADA_VERSION = "1.14.2"
LXD_BRIDGE_NAME = "lxdbr0"


# --- Helper Functions ---


def run_command(
    command, check=True, command_input=None, env=None, capture_output=False
):
    """A helper to run a shell command and handle errors."""
    display_command = " ".join(command)
    if command_input:
        display_command += " <<< [INPUT]"
    print(f"Executing: {display_command}")
    try:
        process_env = os.environ.copy()
        if env:
            process_env.update(env)
        result = subprocess.run(
            command,
            input=command_input,
            check=check,
            text=True,
            env=process_env,
            capture_output=capture_output,
        )
        return result
    except FileNotFoundError:
        print(f"Error: Command '{command[0]}' not found.", file=sys.stderr)
        sys.exit(1)
    except subprocess.CalledProcessError as e:
        if capture_output and e.stderr:
            print(f"Stderr:\n{e.stderr}", file=sys.stderr)
        if check:
            sys.exit(1)
        return e


def command_exists(command):
    """Checks if a command is available in the system's PATH."""
    return shutil.which(command) is not None


# --- Main Installation Logic ---


def install_microk8s():
    """Installs and configures MicroK8s."""
    print("\n--- 1. Setting up MicroK8s ---")
    if not command_exists("microk8s"):
        print("Installing MicroK8s...")
        run_command(["snap", "install", "microk8s", "--classic"])
    else:
        print("MicroK8s is already installed. Skipping.")
    run_command(["microk8s", "status", "--wait-ready"])


def install_lxd_and_configure_network():
    """Installs LXD and robustly configures its network bridge for host connectivity."""
    print("\n--- 2. Setting up LXD and Host Networking ---")
    if not command_exists("lxd"):
        print("Installing LXD...")
        run_command(["snap", "install", "lxd"])
    else:
        print("LXD is already installed. Skipping installation.")

    run_command(["lxd", "init", "--auto"])

    print(f"Configuring LXD network bridge '{LXD_BRIDGE_NAME}'...")
    run_command(["lxc", "network", "set", LXD_BRIDGE_NAME, "ipv4.address=auto"])
    run_command(["lxc", "network", "set", LXD_BRIDGE_NAME, "ipv4.nat=true"])

    print("Restarting LXD daemon to apply configuration...")
    run_command(["systemctl", "restart", "snap.lxd.daemon.service"])
    print("Waiting 10 seconds for LXD daemon to stabilize...")
    time.sleep(10)


def install_docker():
    # (Unchanged)
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
            "Cannot automatically install Docker on non-Debian systems.",
            file=sys.stderr,
        )
        sys.exit(1)


def install_kubectl():
    # (Unchanged)
    print("\n--- 4. Setting up kubectl ---")
    if not command_exists("kubectl"):
        print("Installing kubectl via snap...")
        run_command(["snap", "install", "kubectl", "--classic"])
    else:
        print("kubectl is already installed. Skipping.")


def install_karmada_tools():
    # (Unchanged)
    print(f"\n--- 5. Setting up Karmada CLI Tools (Version: {KARMADA_VERSION}) ---")
    if not command_exists("curl"):
        print("Error: 'curl' is required.", file=sys.stderr)
        sys.exit(1)
    install_env = {"INSTALL_CLI_VERSION": KARMADA_VERSION}
    script_url = "https://raw.githubusercontent.com/karmada-io/karmada/master/hack/install-cli.sh"
    try:
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


def step_6_verify_and_repair_network_setup():
    """Final verification step that also repairs the network state if necessary."""
    print(f"\n--- 6. Verifying and Repairing Network Setup for '{LXD_BRIDGE_NAME}' ---")

    # --- Check and Repair Interface State ---
    print(f"--> Checking administrative state of interface '{LXD_BRIDGE_NAME}'...")
    is_up_administratively = False
    try:
        result = run_command(
            ["ip", "-j", "addr", "show", LXD_BRIDGE_NAME], capture_output=True
        )
        data = json.loads(result.stdout)
        if data and "UP" in data[0].get("flags", []):
            is_up_administratively = True
    except (json.JSONDecodeError, IndexError):
        pass  # Will be handled by the check below

    if not is_up_administratively:
        print(
            f"Interface '{LXD_BRIDGE_NAME}' is not administratively UP. Forcibly bringing it up now..."
        )
        run_command(["ip", "link", "set", LXD_BRIDGE_NAME, "up"])
        time.sleep(2)  # Give the interface a moment to stabilize

    # --- Check and Repair Firewall Rule ---
    print(f"--> Checking firewall FORWARD rule for '{LXD_BRIDGE_NAME}'...")
    check_rule_cmd = [
        "iptables",
        "-C",
        "FORWARD",
        "-i",
        LXD_BRIDGE_NAME,
        "-j",
        "ACCEPT",
    ]
    result = run_command(check_rule_cmd, check=False, capture_output=True)
    if result.returncode != 0:
        print("Firewall rule missing. Adding it now...")
        add_rule_cmd = [
            "iptables",
            "-A",
            "FORWARD",
            "-i",
            LXD_BRIDGE_NAME,
            "-j",
            "ACCEPT",
        ]
        run_command(add_rule_cmd)
    else:
        print("Firewall rule already exists.")

    # --- Final Verification ---
    print("\n--> Final verification of network configuration:")
    all_checks_passed = True
    try:
        result = run_command(
            ["ip", "-j", "addr", "show", LXD_BRIDGE_NAME], capture_output=True
        )
        data = json.loads(result.stdout)

        # CORRECTED: Check for the administrative 'UP' flag, which is the true source of success.
        if data and "UP" in data[0].get("flags", []):
            print(
                f"✅ Verification PASSED: LXD bridge '{LXD_BRIDGE_NAME}' is administratively UP."
            )
        else:
            print(
                f"❌ Verification FAILED: LXD bridge '{LXD_BRIDGE_NAME}' is not administratively UP."
            )
            all_checks_passed = False

        ipv4_info = data[0].get("addr_info", [{}])[0]
        if "local" in ipv4_info:
            print(
                f"✅ Verification PASSED: Host has IP address {ipv4_info['local']} on the bridge."
            )
        else:
            print(
                f"❌ Verification FAILED: Host does not have an IP address on the '{LXD_BRIDGE_NAME}' bridge."
            )
            all_checks_passed = False
    except (json.JSONDecodeError, IndexError):
        print(
            f"❌ Verification FAILED: Could not retrieve IP address info for '{LXD_BRIDGE_NAME}'."
        )
        all_checks_passed = False

    result = run_command(
        ["iptables", "-C", "FORWARD", "-i", LXD_BRIDGE_NAME, "-j", "ACCEPT"],
        check=False,
        capture_output=True,
    )
    if result.returncode == 0:
        print(f"✅ Verification PASSED: iptables FORWARD rule is correctly set.")
    else:
        print(f"❌ Verification FAILED: iptables FORWARD rule is missing.")
        all_checks_passed = False

    return all_checks_passed


# --- Main Execution ---
def main():
    """Main function to run all prerequisite installations."""
    install_microk8s()
    install_lxd_and_configure_network()
    install_docker()
    install_kubectl()
    install_karmada_tools()

    if step_6_verify_and_repair_network_setup():
        print(
            "\n\n✅ --- Prerequisite and Network setup is complete and verified! --- ✅"
        )
    else:
        print(
            "\n\n❌ --- Prerequisite setup complete, and network repair failed! --- ❌"
        )
        print("       Please review the errors above before proceeding.")
        sys.exit(1)


if __name__ == "__main__":
    if os.geteuid() != 0:
        print("This script must be run as the 'root' user.", file=sys.stderr)
        sys.exit(1)
    main()
