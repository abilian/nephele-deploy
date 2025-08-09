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


# --- Helper Functions (unchanged) ---
def run_command(command, check=True, command_input=None, env=None, capture_output=False):
    display_command = " ".join(command)
    if command_input: display_command += " <<< [INPUT]"
    print(f"Executing: {display_command}")
    try:
        process_env = os.environ.copy()
        if env: process_env.update(env)
        result = subprocess.run(
            command, input=command_input, check=check, text=True, env=process_env,
            capture_output=capture_output
        )
        return result
    except FileNotFoundError:
        print(f"Error: Command '{command[0]}' not found.", file=sys.stderr)
        sys.exit(1)
    except subprocess.CalledProcessError as e:
        if capture_output and e.stderr: print(f"Stderr:\n{e.stderr}", file=sys.stderr)
        if check: sys.exit(1)
        return e


def command_exists(command):
    return shutil.which(command) is not None


# --- Main Installation Logic (steps 1, 3, 4, 5 are unchanged) ---
def install_microk8s():
    print("\n--- 1. Setting up MicroK8s ---")
    if not command_exists("microk8s"):
        print("Installing MicroK8s...")
        run_command(["snap", "install", "microk8s", "--classic"])
    else:
        print("MicroK8s is already installed. Skipping.")
    run_command(["microk8s", "status", "--wait-ready"])


def install_lxd_and_configure_network():
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
    print("\n--- 3. Setting up Docker ---")
    if command_exists("docker"):
        print("Docker is already installed. Skipping.")
        return
    if os.path.exists("/etc/debian_version"):
        print("Installing Docker for Debian/Ubuntu...")
        run_command(["apt-get", "update"])
        run_command(["apt-get", "install", "-y", "docker.io"])
    else:
        print("Cannot automatically install Docker on non-Debian systems.", file=sys.stderr)
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
    # ... (content unchanged)
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
    tools_to_install = {"karmadactl": ["bash"], "kubectl-karmada": ["bash", "-s", "kubectl-karmada"]}
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
    print(f"--> Forcibly bringing interface '{LXD_BRIDGE_NAME}' UP...")
    run_command(["ip", "link", "set", LXD_BRIDGE_NAME, "up"])
    time.sleep(2)

    # --- Check and Repair Firewall Rules ---
    print(f"--> Checking and ensuring required firewall rules exist...")
    # Rule 1: Allow traffic passing THROUGH the host FROM containers
    rule1_check = ['iptables', '-C', 'FORWARD', '-i', LXD_BRIDGE_NAME, '-j', 'ACCEPT']
    if run_command(rule1_check, check=False).returncode != 0:
        print("Firewall rule (FORWARD input) missing. Adding it now...")
        run_command(['iptables', '-A', 'FORWARD', '-i', LXD_BRIDGE_NAME, '-j', 'ACCEPT'])

    # Rule 2: Allow traffic passing THROUGH the host TO containers
    rule2_check = ['iptables', '-C', 'FORWARD', '-o', LXD_BRIDGE_NAME, '-j', 'ACCEPT']
    if run_command(rule2_check, check=False).returncode != 0:
        print("Firewall rule (FORWARD output) missing. Adding it now...")
        run_command(['iptables', '-A', 'FORWARD', '-o', LXD_BRIDGE_NAME, '-j', 'ACCEPT'])

    # CRITICAL NEW RULE: Allow traffic FROM the host itself TO the containers
    rule3_check = ['iptables', '-C', 'INPUT', '-i', LXD_BRIDGE_NAME, '-j', 'ACCEPT']
    if run_command(rule3_check, check=False).returncode != 0:
        print("Firewall rule (INPUT) missing. Adding it now...")
        run_command(['iptables', '-A', 'INPUT', '-i', LXD_BRIDGE_NAME, '-j', 'ACCEPT'])

    # --- Final Verification ---
    print("\n--> Final verification of network state:")
    all_checks_passed = True
    try:
        result = run_command(["ip", "-j", "addr", "show", LXD_BRIDGE_NAME], capture_output=True)
        data = json.loads(result.stdout)

        if data and 'UP' in data[0].get('flags', []):
            print(f"✅ Verification PASSED: LXD bridge '{LXD_BRIDGE_NAME}' is administratively UP.")
        else:
            print(f"❌ Verification FAILED: LXD bridge '{LXD_BRIDGE_NAME}' is not administratively UP.")
            all_checks_passed = False

        if 'local' in data[0].get('addr_info', [{}])[0]:
            print(f"✅ Verification PASSED: Host has an IP address on the bridge.")
        else:
            print(f"❌ Verification FAILED: Host does not have an IP address on the bridge.")
            all_checks_passed = False
    except (json.JSONDecodeError, IndexError):
        all_checks_passed = False

    if all(run_command(cmd, check=False).returncode == 0 for cmd in [rule1_check, rule2_check, rule3_check]):
        print(f"✅ Verification PASSED: All 3 required iptables rules are set.")
    else:
        print(f"❌ Verification FAILED: One or more required iptables rules are missing.")
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
        print("\n\n✅ --- Prerequisite and Network setup is complete and verified! --- ✅")
    else:
        print("\n\n❌ --- Prerequisite setup complete, and network repair failed! --- ❌")
        print("       Please review the errors above before proceeding.")
        sys.exit(1)


if __name__ == "__main__":
    if os.geteuid() != 0:
        print("This script must be run as the 'root' user.", file=sys.stderr)
        sys.exit(1)
    main()
