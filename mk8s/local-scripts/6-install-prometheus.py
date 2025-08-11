#!/usr/bin/env python3

"""
This script installs a Prometheus instance into each member cluster using Helm.

Here's what it does:
1.  Adds the official Prometheus community Helm repository.
2.  Retrieves the internal IP address of the host cluster node.
3.  For each member cluster:
    a. Creates a 'monitoring' namespace.
    b. Generates a dynamic Helm values file to configure Prometheus with a
       unique 'source' label and sets the service type to NodePort.
    c. Installs or upgrades the 'prometheus' Helm chart.
4.  Waits for all Prometheus pods across all member clusters to become ready.
5.  Sets up LXD port-forwarding to expose each Prometheus instance on the host.
6.  Performs an HTTP check to verify each Prometheus UI is accessible.
7.  Includes a robust cleanup function to uninstall Helm releases and remove resources.
"""

import os
import sys
import time
import json
import tempfile
import http.client

# Import shared configuration and helpers
from common import run_command, check_root_privileges, print_color, colors
from config import (
    MEMBER_CLUSTERS,
    HOST_KUBECONFIG,
    CONFIG_FILES_DIR,
)

# --- Configuration ---
PROMETHEUS_HELM_REPO_URL = "https://prometheus-community.github.io/helm-charts"
PROMETHEUS_HELM_REPO_NAME = "prometheus-community"
HELM_CHART_NAME = f"{PROMETHEUS_HELM_REPO_NAME}/prometheus"
NAMESPACE = "monitoring"

# We will assign a unique NodePort and a corresponding host port for each member
PROMETHEUS_PORTS = {
    "member1": {"node_port": 30091, "host_port": 9091},
    "member2": {"node_port": 30092, "host_port": 9092},
    "member3": {"node_port": 30093, "host_port": 9093},
}


def create_temp_file(content):
    """Creates a temporary file and returns its path."""
    with tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".yaml") as f:
        f.write(content)
        return f.name


def setup_helm_repository():
    """Adds and updates the Prometheus Helm repository."""
    print_color(colors.YELLOW, "\n--- 1. Setting up Helm Repository ---")
    run_command(["helm", "repo", "add", PROMETHEUS_HELM_REPO_NAME, PROMETHEUS_HELM_REPO_URL])
    run_command(["helm", "repo", "update"])
    print_color(colors.GREEN, "✅ Helm repository is ready.")


def get_host_cluster_ip():
    """Retrieves the internal IP of the host cluster's node."""
    print("--> Getting host cluster's internal IP for remoteWrite configuration...")
    cmd = [
        "kubectl", "--kubeconfig", HOST_KUBECONFIG, "get", "nodes",
        "-o", "jsonpath={.items[0].status.addresses[?(@.type=='InternalIP')].address}",
    ]
    result = run_command(cmd, capture_output=True)
    host_ip = result.stdout.strip()
    if not host_ip:
        print_color(colors.RED, "FATAL: Could not retrieve host cluster IP.")
        sys.exit(1)
    print(f"--> Host cluster IP found: {host_ip}")
    return host_ip


def install_prometheus_on_member(member, host_ip, temp_files_list):
    """Installs the Prometheus chart on a single member cluster."""
    print_color(colors.YELLOW, f"\n--- Installing Prometheus on {member} ---")
    member_kubeconfig = os.path.join(CONFIG_FILES_DIR, f"{member}.config")
    helm_release_name = f"prometheus-{member}"
    ports = PROMETHEUS_PORTS[member]

    # Create the monitoring namespace
    run_command(["kubectl", "--kubeconfig", member_kubeconfig, "create", "namespace", NAMESPACE], check=False)

    # Dynamically generate the Helm values file content
    values_yaml = f"""
prometheus:
  prometheusSpec:
    externalLabels:
      source: {member}
    # remoteWrite:
    #   - url: "http://{host_ip}:9090/api/v1/write" # Placeholder for a central Prometheus
  server:
    service:
      type: NodePort
      nodePort: {ports['node_port']}
"""
    values_file_path = create_temp_file(values_yaml)
    temp_files_list.append(values_file_path)

    # Use 'helm upgrade --install' to make the operation idempotent
    helm_install_cmd = [
        "helm", "upgrade", "--install", helm_release_name, HELM_CHART_NAME,
        "--kubeconfig", member_kubeconfig,
        "--namespace", NAMESPACE,
        "-f", values_file_path,
    ]
    run_command(helm_install_cmd)


def verify_installations():
    """Waits for Prometheus pods to be ready and verifies HTTP access."""
    print_color(colors.YELLOW, "\n--- 3. Verifying Prometheus Installations ---")

    # First, expose all services via LXD port forwarding
    for member, ports in PROMETHEUS_PORTS.items():
        proxy_name = f"proxy-prometheus-{member}"
        run_command(["lxc", "config", "device", "remove", member, proxy_name], check=False)
        run_command([
            "lxc", "config", "device", "add", member, proxy_name, "proxy",
            f"listen=tcp:0.0.0.0:{ports['host_port']}",
            f"connect=tcp:127.0.0.1:{ports['node_port']}",
        ])

    # Now, wait for pods to be ready
    print("--> Waiting up to 180 seconds for all Prometheus pods to become ready...")
    for i in range(18): # 18 * 10s = 3 minutes
        all_ready = True
        for member in MEMBER_CLUSTERS:
            member_kubeconfig = os.path.join(CONFIG_FILES_DIR, f"{member}.config")
            cmd = ["kubectl", "--kubeconfig", member_kubeconfig, "get", "pods", "-n", NAMESPACE, "-l", "app=prometheus,component=server", "-o", "json"]
            result = run_command(cmd, check=False, capture_output=True)
            if result.returncode != 0:
                all_ready = False
                break

            pods = json.loads(result.stdout).get("items", [])
            if not pods or not any(p.get("status", {}).get("phase") == "Running" for p in pods):
                all_ready = False
                break

        if all_ready:
            print_color(colors.GREEN, "✅ All Prometheus server pods are running.")
            break

        print(f"Not all pods are ready yet. Retrying in 10s...")
        time.sleep(10)
    else:
        print_color(colors.RED, "❌ FAILED: Timed out waiting for pods.")
        return False

    # Finally, verify HTTP access
    print("\n--> Verifying HTTP access to each Prometheus instance...")
    all_accessible = True
    time.sleep(5) # Give proxies a moment
    for member, ports in PROMETHEUS_PORTS.items():
        print(f"--> Checking connection to {member} (http://localhost:{ports['host_port']})...")
        try:
            conn = http.client.HTTPConnection("localhost", ports['host_port'], timeout=15)
            conn.request("GET", "/graph")
            response = conn.getresponse()
            if response.status == 200:
                print_color(colors.GREEN, f"  - ✅ SUCCESS: Received HTTP 200 OK.")
            else:
                print_color(colors.RED, f"  - ❌ FAILED: Received unexpected status HTTP {response.status}.")
                all_accessible = False
            conn.close()
        except Exception as e:
            print_color(colors.RED, f"  - ❌ FAILED: Could not connect. Error: {e}")
            all_accessible = False

    return all_accessible


def cleanup(temp_files_list):
    """Uninstalls Helm releases and removes all created resources."""
    print_color(colors.YELLOW, "\n--- Cleaning up Prometheus resources ---")
    for member in MEMBER_CLUSTERS:
        print(f"--> Cleaning up {member}...")
        member_kubeconfig = os.path.join(CONFIG_FILES_DIR, f"{member}.config")
        helm_release_name = f"prometheus-{member}"
        # Uninstall Helm release
        run_command(["helm", "uninstall", helm_release_name, "--kubeconfig", member_kubeconfig, "-n", NAMESPACE], check=False)
        # Delete the namespace
        run_command(["kubectl", "delete", "namespace", NAMESPACE, "--kubeconfig", member_kubeconfig], check=False)
        # Remove LXD proxy device
        run_command(["lxc", "config", "device", "remove", member, f"proxy-prometheus-{member}"], check=False)

    for f in temp_files_list:
        if os.path.exists(f):
            os.remove(f)
    print_color(colors.GREEN, "✅ Prometheus cleanup complete.")


def main():
    """Orchestrates the installation and verification of Prometheus."""
    check_root_privileges("8-install-prometheus.py")
    temp_files = []
    all_ok = False

    try:
        setup_helm_repository()
        host_ip = get_host_cluster_ip()

        print("\n--- 2. Installing Prometheus on all Member Clusters ---")
        for member in MEMBER_CLUSTERS:
            install_prometheus_on_member(member, host_ip, temp_files)

        if not verify_installations():
            sys.exit(1)

        print_color(colors.GREEN, "\n\n✅ --- Prometheus installed and verified successfully on all member clusters! --- ✅")
        print("\nYou can access the UIs on the following ports on your host:")
        for member, ports in PROMETHEUS_PORTS.items():
            print_color(colors.YELLOW, f"  - {member}: http://localhost:{ports['host_port']}")
        all_ok = True

    finally:
        if not all_ok:
            print_color(colors.RED, "\nOne or more steps failed. Proceeding with cleanup...")

        # Give user time to see the URLs before cleaning up
        if all_ok:
            input("\nPress Enter to continue and clean up all Prometheus resources...")

        cleanup(temp_files)


if __name__ == "__main__":
    main()
