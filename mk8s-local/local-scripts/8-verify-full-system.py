#!/usr/bin/env python3

"""
This script performs an end-to-end verification of the entire Karmada setup.

It checks each layer of the architecture, from the host services down to the
deployed applications, and validates that the live state matches the expected
configuration. It provides detailed error messages on failure and exits with a
non-zero status code if any check fails.
"""

import sys
import os.path

from common import run_command, print_color, colors
from config import (
    MEMBER_CLUSTERS,
    KARMADA_KUBECONFIG,
    CONFIG_FILES_DIR,
)

# --- Global State ---
ALL_OK = True

# --- Configuration for Verification ---
MEMBER_API_PORTS = {"member1": "16441", "member2": "16442", "member3": "16444"}
API_PROXY_NAME = "proxy-k8s"

FLASK_PROXY_NAME = "proxy-simple-flask"
FLASK_HOST_PORTS = {"member1": "32301", "member2": "32302", "member3": "32303"}

PROMETHEUS_HOST_PORTS = {"member1": "9091", "member2": "9092", "member3": "9093"}


def check(description, command, expected_output=None, expected_rc=0):
    """
    Runs a command, checks its return code and optionally its output,
    and reports a detailed pass/fail message.
    """
    global ALL_OK
    print_color(colors.GRAY, f"  > Checking: {description}")

    # Use capture_output=True only if we need to check the output
    capture = expected_output is not None

    result = run_command(command, check=False, capture_output=capture)

    success = result.returncode == expected_rc
    if success and expected_output is not None:
        success = result.stdout.strip() == expected_output

    if success:
        print_color(colors.GREEN, "  [✅ PASSED]")
        return True
    else:
        print_color(colors.RED, "  [❌ FAILED]")
        print_color(colors.GRAY, f"    - Command: {' '.join(command)}")
        if result.returncode != expected_rc:
            print_color(
                colors.RED,
                f"    - Reason: Expected return code {expected_rc}, but got {result.returncode}.",
            )
        if expected_output is not None and result.stdout.strip() != expected_output:
            print_color(colors.RED, f"    - Reason: Output mismatch.")
            print_color(colors.RED, f"    - Expected: '{expected_output}'")
            print_color(colors.RED, f"    -      Got: '{result.stdout.strip()}'")
        if result.stderr:
            print_color(colors.RED, f"    - Stderr: {result.stderr.strip()}")
        ALL_OK = False
        return False


def main():
    """Orchestrates the entire system verification process."""
    global ALL_OK

    print_color(
        colors.BLUE, "\n========================================================"
    )
    print_color(colors.BLUE, " Kicking off Full System Verification")
    print_color(colors.BLUE, "========================================================")

    # --- Layer 1: Host Services ---
    print_color(colors.YELLOW, "\n--- Layer 1: Verifying Host Services ---")
    check(
        "Host MicroK8s cluster is running and ready",
        ["microk8s", "status", "--wait-ready"],
    )
    check(
        "LXD daemon is active",
        ["systemctl", "is-active", "--quiet", "snap.lxd.daemon.service"],
    )

    # FIXME
    # check("MicroK8s registry addon is enabled", ["bash", "-c", "microk8s status | grep -q 'registry: enabled'"])

    # --- Layer 2: Karmada Control Plane ---
    print_color(colors.YELLOW, "\n--- Layer 2: Verifying Karmada Control Plane ---")
    check(
        "Karmada API server is responsive",
        ["kubectl", "--kubeconfig", KARMADA_KUBECONFIG, "api-resources"],
    )
    for member in MEMBER_CLUSTERS:
        cmd = [
            "kubectl",
            "--kubeconfig",
            KARMADA_KUBECONFIG,
            "get",
            "cluster",
            member,
            "-o",
            "jsonpath={.status.conditions[?(@.type=='Ready')].status}",
        ]
        check(
            f"Member cluster '{member}' is registered and Ready",
            cmd,
            expected_output="True",
        )

    # --- Layer 3: Member Cluster APIs & Proxies ---
    print_color(
        colors.YELLOW, "\n--- Layer 3: Verifying Member Cluster API Proxies ---"
    )
    for member, port in MEMBER_API_PORTS.items():
        check(
            f"Host is listening on port {port} for '{member}'",
            ["bash", "-c", f"ss -tlpn | grep -q ':{port}'"],
        )
        cmd = ["lxc", "config", "device", "get", member, API_PROXY_NAME, "connect"]
        check(
            f"LXD proxy for '{member}' API correctly targets internal API",
            cmd,
            expected_output="tcp:127.0.0.1:16443",
        )

    # --- Layer 4: Deployed Applications ---
    print_color(colors.YELLOW, "\n--- Layer 4: Verifying Deployed Applications ---")

    # 4a: Custom Flask App Verification
    for member, host_port in FLASK_HOST_PORTS.items():
        print_color(colors.BLUE, f"\n--> Verifying Flask Demo on '{member}'")
        member_kubeconfig = os.path.join(CONFIG_FILES_DIR, f"{member}.config")

        svc_cmd = [
            "kubectl",
            "--kubeconfig",
            member_kubeconfig,
            "get",
            "svc",
            "custom-flask-demo-simple-service",
            "-o",
            "jsonpath={.spec.ports[0].nodePort}",
        ]
        node_port_res = run_command(svc_cmd, check=False, capture_output=True)
        if node_port_res.returncode != 0:
            print_color(
                colors.RED,
                f"  [❌ FAILED] - Could not find NodePort for Flask service on '{member}'.",
            )
            ALL_OK = False
            continue
        node_port = node_port_res.stdout.strip()
        print_color(
            colors.GREEN, f"  [INFO] Found Flask service with NodePort: {node_port}"
        )

        proxy_cmd = [
            "lxc",
            "config",
            "device",
            "get",
            member,
            FLASK_PROXY_NAME,
            "connect",
        ]
        expected_target = f"tcp:127.0.0.1:{node_port}"
        check(
            f"LXD proxy correctly targets the Flask service NodePort",
            proxy_cmd,
            expected_output=expected_target,
        )

        check(
            f"Flask application is accessible at http://localhost:{host_port}",
            ["curl", "-sfL", f"http://localhost:{host_port}"],
        )

    # 4b: Prometheus Verification
    for member, host_port in PROMETHEUS_HOST_PORTS.items():
        print_color(colors.BLUE, f"\n--> Verifying Prometheus Demo on '{member}'")
        member_kubeconfig = os.path.join(CONFIG_FILES_DIR, f"{member}.config")
        helm_release_name = f"prometheus-{member}"

        pod_cmd = [
            "kubectl",
            "--kubeconfig",
            member_kubeconfig,
            "get",
            "pods",
            "-n",
            "monitoring",
            "-l",
            f"app.kubernetes.io/name=prometheus,app.kubernetes.io/instance={helm_release_name}",
            "-o",
            "jsonpath={.items[0].status.podIP}",
        ]
        pod_ip_res = run_command(pod_cmd, check=False, capture_output=True)
        if pod_ip_res.returncode != 0:
            print_color(
                colors.RED,
                f"  [❌ FAILED] - Could not find running Prometheus pod on '{member}'.",
            )
            ALL_OK = False
            continue
        pod_ip = pod_ip_res.stdout.strip()
        print_color(colors.GREEN, f"  [INFO] Found Prometheus pod with IP: {pod_ip}")

        proxy_cmd = [
            "lxc",
            "config",
            "device",
            "get",
            member,
            f"proxy-prometheus-{member}",
            "connect",
        ]
        expected_target = f"tcp:{pod_ip}:9090"
        check(
            f"LXD proxy correctly targets the Prometheus pod IP",
            proxy_cmd,
            expected_output=expected_target,
        )

        check(
            f"Prometheus application is accessible at http://localhost:{host_port}",
            ["curl", "-sfL", f"http://localhost:{host_port}"],
        )

    # --- Final Summary ---
    print_color(
        colors.BLUE, "\n========================================================"
    )
    if ALL_OK:
        print_color(
            colors.GREEN, "✅✅✅ All system checks passed successfully! ✅✅✅"
        )
        sys.exit(0)
    else:
        print_color(colors.RED, "❌❌❌ One or more system checks failed. ❌❌❌")
        sys.exit(1)


if __name__ == "__main__":
    main()
