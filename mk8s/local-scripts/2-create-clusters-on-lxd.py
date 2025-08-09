#!/usr/bin/env python3

import subprocess
import sys
import os
import json
import time
from pwd import getpwnam

# --- Configuration ---
MEMBER_CLUSTERS = ["member1", "member2", "member3"]
LXD_PROFILE_NAME = "microk8s"

# NEW: Define a mapping of host ports to the container's API server port
PORT_MAPPING = {
    "member1": "16441",
    "member2": "16442",
    "member3": "16443",  # Note: This might conflict if the host MicroK8s uses 16443. We'll proceed for now.
}
CONTAINER_API_PORT = "16443"

# (LXD_PROFILE_CONFIG is unchanged)
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


# --- Helper Functions (unchanged) ---
def run_command(command, check=True, command_input=None, capture_output=False):
    print(f"Executing: {' '.join(command)}")
    try:
        result = subprocess.run(
            command, input=command_input, check=check, text=True,
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


def container_exists(name):
    return subprocess.run(['lxc', 'info', name], capture_output=True).returncode == 0


def set_correct_owner(filepath):
    user_name = os.environ.get('SUDO_USER', "root")
    user_info = getpwnam(user_name)
    os.chown(filepath, user_info.pw_uid, user_info.pw_gid)


def setup_lxd_profile():
    print(f"--- Checking for LXD profile '{LXD_PROFILE_NAME}' ---")
    result = run_command(['lxc', 'profile', 'list', '--format', 'json'], capture_output=True)
    profiles = [p['name'] for p in json.loads(result.stdout)]
    if LXD_PROFILE_NAME not in profiles:
        print(f"Profile '{LXD_PROFILE_NAME}' not found. Creating it now...")
        run_command(['lxc', 'profile', 'create', LXD_PROFILE_NAME])
        run_command(['lxc', 'profile', 'edit', LXD_PROFILE_NAME], command_input=LXD_PROFILE_CONFIG)
    else:
        print(f"Profile '{LXD_PROFILE_NAME}' already exists.")


# --- Main Logic ---

def main():
    setup_lxd_profile()
    print("\n--- Provisioning 3 MicroK8s clusters using LXD ---")
    for member in MEMBER_CLUSTERS:
        print(f"\n>>> Processing cluster: {member}")
        if not container_exists(member):
            print(f"Launching new LXD container for {member}...")
            run_command(
                ['lxc', 'launch', 'ubuntu:22.04', member, '--profile', 'default', '--profile', LXD_PROFILE_NAME])
        else:
            print(f"Container '{member}' already exists. Re-using.")

        print(f"Waiting for cloud-init to finish in {member}...")
        run_command(['lxc', 'exec', member, '--', 'cloud-init', 'status', '--wait'])

        print(f"Installing MicroK8s in {member}...")
        install_cmd = 'if ! command -v microk8s &> /dev/null; then sudo snap install microk8s --classic; else echo "MicroK8s already installed."; fi'
        run_command(['lxc', 'exec', member, '--', '/bin/bash', '-c', install_cmd])
        run_command(['lxc', 'exec', member, '--', 'sudo', 'microk8s', 'status', '--wait-ready'])
        run_command(['lxc', 'exec', member, '--', 'sudo', 'microk8s', 'enable', 'dns', 'storage'])

        # NEW: Setup the port-forwarding proxy device in LXD
        host_port = PORT_MAPPING[member]
        print(f"Setting up port forward: localhost:{host_port} -> container:{CONTAINER_API_PORT} for {member}...")
        # The device name is arbitrary, 'proxy-k8s' is clear
        proxy_command = [
            'lxc', 'config', 'device', 'add', member, 'proxy-k8s', 'proxy',
            f'listen=tcp:0.0.0.0:{host_port}',  # Listen on all host interfaces
            f'connect=tcp:127.0.0.1:{CONTAINER_API_PORT}'  # Connect to the service inside the container
        ]
        # We use check=False because this command fails if the device already exists, which is safe.
        run_command(proxy_command, check=False)

        print(f"Extracting and modifying kubeconfig for {member}...")
        kubeconfig_path = f"/root/{member}.config"
        result = run_command(['lxc', 'exec', member, '--', 'sudo', 'microk8s', 'config'], capture_output=True)

        # Modify the kubeconfig content BEFORE writing it to a file
        kubeconfig_content = result.stdout
        # CRITICAL: Replace the server address with the localhost and the forwarded port
        modified_content = kubeconfig_content.replace(f'server: https://127.0.0.1:{CONTAINER_API_PORT}',
                                                      f'server: https://127.0.0.1:{host_port}')

        with open(kubeconfig_path, 'w') as f:
            f.write(modified_content)
        set_correct_owner(kubeconfig_path)

        print(f">>> Successfully processed cluster: {member}. Kubeconfig points to localhost:{host_port}")

    print("\n--- All member clusters are ready! ---")


if __name__ == "__main__":
    if os.geteuid() != 0:
        print("This script must be run as the 'root' user.", file=sys.stderr)
        sys.exit(1)
    main()
