#!/usr/bin/env python3

"""
This script installs a Prometheus instance into each member cluster using Helm.

It uses a robust method of exposing the service by creating an LXD proxy
that connects directly to the Pod's internal IP and the correct container port (9090).
"""

import os
import sys
import time
import json
import tempfile
import http.client

# Import shared configuration and helpers
from common import run_command, check_root_privileges, print_color, colors
from config import MEMBER_CLUSTERS, HOST_KUBECONFIG, CONFIG_FILES_DIR

# --- Configuration ---
PROMETHEUS_HELM_REPO_URL = "https://prometheus-community.github.io/helm-charts"
PROMETHEUS_HELM_REPO_NAME = "prometheus-community"
HELM_CHART_NAME = f"{PROMETHEUS_HELM_REPO_NAME}/prometheus"
NAMESPACE = "monitoring"
PROMETHEUS_HOST_PORTS = {"member1": 9091, "member2": 9092, "member3": 9093}
# --- The correct default port for the Prometheus server ---
PROMETHEUS_CONTAINER_PORT = 9090


def create_temp_file(content):
    with tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".yaml") as f:
        f.write(content)
        return f.name


def setup_helm_repository():
    print_color(colors.YELLOW, "\n--- 1. Setting up Helm Repository ---")
    run_command(
        ["helm", "repo", "add", PROMETHEUS_HELM_REPO_NAME, PROMETHEUS_HELM_REPO_URL]
    )
    run_command(["helm", "repo", "update"])
    print_color(colors.GREEN, "✅ Helm repository is ready.")


def install_prometheus_on_members(temp_files_list):
    print_color(
        colors.YELLOW, f"\n--- 2. Installing Prometheus on all Member Clusters ---"
    )
    for member in MEMBER_CLUSTERS:
        print_color(colors.BLUE, f"\n--> Processing cluster: {member}")
        member_kubeconfig = os.path.join(CONFIG_FILES_DIR, f"{member}.config")
        helm_release_name = f"prometheus-{member}"
        run_command(
            [
                "kubectl",
                "--kubeconfig",
                member_kubeconfig,
                "create",
                "namespace",
                NAMESPACE,
            ],
            check=False,
        )
        values_yaml = f"""
        alertmanager:
          enabled: false
        pushgateway:
          enabled: false
        server:
          persistentVolume:
            enabled: false
        """
        values_file_path = create_temp_file(values_yaml)
        temp_files_list.append(values_file_path)
        helm_install_cmd = [
            "helm",
            "upgrade",
            "--install",
            helm_release_name,
            HELM_CHART_NAME,
            "--kubeconfig",
            member_kubeconfig,
            "--namespace",
            NAMESPACE,
            "-f",
            values_file_path,
        ]
        run_command(helm_install_cmd)


def verify_and_expose_installations():
    print_color(
        colors.YELLOW, "\n--- 3. Verifying and Exposing Prometheus Installations ---"
    )
    print("--> Waiting up to 180 seconds for all Prometheus pods to become ready...")
    ready_pods_info = {}
    for i in range(18):
        for member in MEMBER_CLUSTERS:
            if member in ready_pods_info:
                continue
            member_kubeconfig = os.path.join(CONFIG_FILES_DIR, f"{member}.config")
            helm_release_name = f"prometheus-{member}"
            label_selector = f"app.kubernetes.io/name=prometheus,app.kubernetes.io/instance={helm_release_name}"
            cmd = [
                "kubectl",
                "--kubeconfig",
                member_kubeconfig,
                "get",
                "pods",
                "-n",
                NAMESPACE,
                "-l",
                label_selector,
                "-o",
                "json",
            ]
            result = run_command(cmd, check=False, capture_output=True)
            if result.returncode == 0:
                pods = json.loads(result.stdout).get("items", [])
                if (
                    pods
                    and pods[0].get("status", {}).get("phase") == "Running"
                    and all(
                        cs.get("ready")
                        for cs in pods[0].get("status", {}).get("containerStatuses", [])
                    )
                ):
                    pod_info = pods[0]
                    pod_ip = pod_info["status"]["podIP"]
                    ready_pods_info[member] = {"ip": pod_ip}
                    print_color(
                        colors.GREEN, f"✅ Prometheus pod for {member} is Ready."
                    )
        if len(ready_pods_info) == len(MEMBER_CLUSTERS):
            break
        print(
            f"Waiting for pods... ({len(ready_pods_info)}/{len(MEMBER_CLUSTERS)} ready). Retrying in 10s..."
        )
        time.sleep(10)
    else:
        print_color(colors.RED, "❌ FAILED: Timed out waiting for pods.")
        return False

    print(
        "\n--> Creating LXD proxy devices linked directly to each Pod IP and correct port (9090)..."
    )
    for member, host_port in PROMETHEUS_HOST_PORTS.items():
        pod_ip = ready_pods_info[member]["ip"]
        print(
            f"    - For {member}: Found Pod IP {pod_ip}, connecting to port {PROMETHEUS_CONTAINER_PORT}"
        )
        proxy_name = f"proxy-prometheus-{member}"
        run_command(
            ["lxc", "config", "device", "remove", member, proxy_name], check=False
        )
        print(
            f"    - Creating proxy: host:{host_port} -> container (pod):{pod_ip}:{PROMETHEUS_CONTAINER_PORT}"
        )
        run_command(
            [
                "lxc",
                "config",
                "device",
                "add",
                member,
                proxy_name,
                "proxy",
                f"listen=tcp:0.0.0.0:{host_port}",
                f"connect=tcp:{pod_ip}:{PROMETHEUS_CONTAINER_PORT}",
            ]
        )

    print("\n--> Verifying HTTP access to each Prometheus instance...")
    all_accessible = True
    time.sleep(5)
    for member, host_port in PROMETHEUS_HOST_PORTS.items():
        print(f"--> Checking connection to {member} (http://localhost:{host_port})...")
        try:
            conn = http.client.HTTPConnection("localhost", host_port, timeout=15)
            conn.request("GET", "/query")
            response = conn.getresponse()
            if response.status == 200:
                print_color(colors.GREEN, f"  - ✅ SUCCESS: Received HTTP 200 OK.")
            else:
                print_color(
                    colors.RED,
                    f"  - ❌ FAILED: Received unexpected status HTTP {response.status}. Body: {response.read().decode('utf-8', 'ignore')}",
                )
                all_accessible = False
            conn.close()
        except Exception as e:
            print_color(colors.RED, f"  - ❌ FAILED: Could not connect. Error: {e}")
            all_accessible = False
    return all_accessible


def cleanup(temp_files_list):
    print_color(colors.YELLOW, "\n--- Cleaning up Prometheus resources ---")
    for member in MEMBER_CLUSTERS:
        print(f"--> Cleaning up {member}...")
        member_kubeconfig = os.path.join(CONFIG_FILES_DIR, f"{member}.config")
        helm_release_name = f"prometheus-{member}"
        run_command(
            [
                "helm",
                "uninstall",
                helm_release_name,
                "--kubeconfig",
                member_kubeconfig,
                "-n",
                NAMESPACE,
            ],
            check=False,
        )
        run_command(
            [
                "kubectl",
                "delete",
                "namespace",
                NAMESPACE,
                "--kubeconfig",
                member_kubeconfig,
            ],
            check=False,
        )
        run_command(
            ["lxc", "config", "device", "remove", member, f"proxy-prometheus-{member}"],
            check=False,
        )
    for f in temp_files_list:
        if os.path.exists(f):
            os.remove(f)
    print_color(colors.GREEN, "✅ Prometheus cleanup complete.")


def main():
    check_root_privileges("8-install-prometheus.py")
    temp_files = []
    all_ok = False
    try:
        setup_helm_repository()
        install_prometheus_on_members(temp_files)
        if not verify_and_expose_installations():
            sys.exit(1)
        print_color(
            colors.GREEN,
            "\n\n✅ --- Prometheus installed and verified successfully on all member clusters! --- ✅",
        )
        print("\nYou can access the UIs on the following ports on your host:")
        for member, host_port in PROMETHEUS_HOST_PORTS.items():
            print_color(
                colors.YELLOW, f"  - {member}: http://localhost:{host_port}/graph"
            )
        all_ok = True
    finally:
        pass
        # if not all_ok: print_color(colors.RED, "\nOne or more steps failed. Proceeding with cleanup...")
        # if all_ok: input("\nPress Enter to continue and clean up all Prometheus resources...")
        # cleanup(temp_files)


if __name__ == "__main__":
    main()
