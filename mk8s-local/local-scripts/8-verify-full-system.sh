#!/bin/bash

# ==============================================================================
# 9-verify-full-system.sh
#
# This script performs an end-to-end verification of the entire Karmada setup.
# It checks each layer of the architecture, from the host services down to the
# deployed applications, and validates that the live state matches the
# expected configuration. It provides detailed error messages on failure.
#
# It will exit with a non-zero status code if any check fails.
# ==============================================================================

# --- Script Configuration ---
# Use 'set -x' to echo every command before it is executed.
set -o xtrace
set -o pipefail

# --- Color Definitions ---
GREEN='\033[0;32m'
RED='\033[0;31m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
GRAY='\033[0;90m'
NC='\033[0m' # No Color

# --- Global State ---
ALL_OK=true
MEMBER_CLUSTERS=("member1" "member2" "member3")
HOST_KUBECONFIG="/var/snap/microk8s/current/credentials/client.config"
KARMADA_KUBECONFIG="/etc/karmada/karmada-apiserver.config"
CONFIG_FILES_DIR="/root"

# --- Helper Functions ---

print_color() {
    # Turn off xtrace for this function to avoid clutter
    { set +x; } 2>/dev/null
    printf "%b%s%b\n" "$1" "$2" "$NC"
    set -x
}

# Simplified check function
check() {
    local description="$1"
    print_color "$GRAY" "  > Checking: $description"
}

on_success() {
    print_color "$GREEN" "  [✅ PASSED]"
}

on_fail() {
    local message="$1"
    print_color "$RED" "  [❌ FAILED] - ${message}"
    ALL_OK=false
}

# --- Main Verification Logic ---

print_color "$BLUE" "\n========================================================"
print_color "$BLUE" " Kicking off Full System Verification"
print_color "$BLUE" "========================================================"

# --- Layer 1: Host Services ---
print_color "$YELLOW" "\n--- Layer 1: Verifying Host Services ---"
check "Host MicroK8s cluster is running and ready"
microk8s status --wait-ready &> /dev/null && on_success || on_fail "MicroK8s is not in a ready state."

check "LXD daemon is active"
systemctl is-active --quiet snap.lxd.daemon.service && on_success || on_fail "The LXD snap daemon is not active."

check "Local Container Registry is listening on port 32000"
ss -tlpn | grep -q 'LISTEN.*:32000' && on_success || on_fail "MicroK8s registry is not listening on port 32000."

# --- Layer 2: Karmada Control Plane ---
print_color "$YELLOW" "\n--- Layer 2: Verifying Karmada Control Plane ---"
check "Karmada API server is responsive"
kubectl --kubeconfig "$KARMADA_KUBECONFIG" api-resources &> /dev/null && on_success || on_fail "Could not connect to the Karmada API server."

for member in "${MEMBER_CLUSTERS[@]}"; do
    check "Member cluster '$member' is registered and Ready"
    status=$(kubectl --kubeconfig "$KARMADA_KUBECONFIG" get cluster "$member" -o jsonpath='{.status.conditions[?(@.type=="Ready")].status}' 2>/dev/null)
    [[ "$status" == "True" ]] && on_success || on_fail "Expected status 'True', but got '$status'."
done

# --- Layer 3: Member Cluster APIs & Proxies ---
print_color "$YELLOW" "\n--- Layer 3: Verifying Member Cluster API Proxies ---"
MEMBER_PORTS=("16441" "16442" "16444")
API_PROXY_NAME="proxy-k8s"
for i in "${!MEMBER_CLUSTERS[@]}"; do
    member="${MEMBER_CLUSTERS[$i]}"
    port="${MEMBER_PORTS[$i]}"

    check "Host is listening on port $port for '$member'"
    ss -tlpn | grep -q ":$port" && on_success || on_fail "Port $port is not open on the host."

    check "LXD proxy for '$member' API correctly targets internal API server"
    connect_target=$(lxc config device get "$member" "$API_PROXY_NAME" connect 2>/dev/null)
    [[ "$connect_target" == "tcp:127.0.0.1:16443" ]] && on_success || on_fail "Expected 'tcp:127.0.0.1:16443', but got '$connect_target'."
done

# --- Layer 4: Deployed Applications ---
print_color "$YELLOW" "\n--- Layer 4: Verifying Deployed Applications ---"

# 4a: Custom Flask App Verification
FLASK_PROXY_NAME="proxy-simple-flask"
FLASK_HOST_PORTS=("32301" "32302" "32303")
for i in "${!MEMBER_CLUSTERS[@]}"; do
    member="${MEMBER_CLUSTERS[$i]}"
    host_port="${FLASK_HOST_PORTS[$i]}"
    member_kubeconfig="${CONFIG_FILES_DIR}/${member}.config"

    print_color "$BLUE" "\n--> Verifying Flask Demo on '$member'"

    # NOTE: The Flask demo uses a NodePort service. We verify the proxy points to it.
    node_port=$(kubectl --kubeconfig "$member_kubeconfig" get svc custom-flask-demo-simple-service -o jsonpath='{.spec.ports[0].nodePort}' 2>/dev/null)
    if [[ -z "$node_port" ]]; then on_fail "Could not find NodePort for Flask service."; continue; fi
    print_color "$GREEN" "  [INFO] Found Flask service with NodePort: $node_port"

    check "LXD proxy correctly targets the Flask service NodePort"
    connect_target=$(lxc config device get "$member" "$FLASK_PROXY_NAME" connect 2>/dev/null)
    [[ "$connect_target" == "tcp:127.0.0.1:$node_port" ]] && on_success || on_fail "Expected 'tcp:127.0.0.1:$node_port', but got '$connect_target'."

    check "Flask application is accessible at http://localhost:$host_port"
    curl -sfL "http://localhost:$host_port" &> /dev/null && on_success || on_fail "Could not connect or received non-2xx/3xx response."
done

# 4b: Prometheus Verification
PROMETHEUS_HOST_PORTS=("9091" "9092" "9093")
for i in "${!MEMBER_CLUSTERS[@]}"; do
    member="${MEMBER_CLUSTERS[$i]}"
    host_port="${PROMETHEUS_HOST_PORTS[$i]}"
    member_kubeconfig="${CONFIG_FILES_DIR}/${member}.config"
    helm_release_name="prometheus-$member"
    proxy_name="proxy-prometheus-$member"

    print_color "$BLUE" "\n--> Verifying Prometheus Demo on '$member'"

    # NOTE: The Prometheus demo proxies directly to the Pod IP.
    pod_ip=$(kubectl --kubeconfig "$member_kubeconfig" get pods -n monitoring -l "app.kubernetes.io/name=prometheus,app.kubernetes.io/instance=$helm_release_name" -o jsonpath='{.items[0].status.podIP}' 2>/dev/null)
    if [[ -z "$pod_ip" ]]; then on_fail "Could not find running Prometheus pod."; continue; fi
    print_color "$GREEN" "  [INFO] Found Prometheus pod with IP: $pod_ip"

    check "LXD proxy correctly targets the Prometheus pod IP"
    connect_target=$(lxc config device get "$member" "$proxy_name" connect 2>/dev/null)
    [[ "$connect_target" == "tcp:$pod_ip:9090" ]] && on_success || on_fail "Expected 'tcp:$pod_ip:9090', but got '$connect_target'."

    check "Prometheus application is accessible at http://localhost:$host_port"
    curl -sfL "http://localhost:$host_port" &> /dev/null && on_success || on_fail "Could not connect or received non-2xx/3xx response."
done

# --- Final Summary ---
{ set +x; } 2>/dev/null
print_color "$BLUE" "\n========================================================"
if [ "$ALL_OK" = true ]; then
    print_color "$GREEN" "✅✅✅ All system checks passed successfully! ✅✅✅"
    exit 0
else
    print_color "$RED" "❌❌❌ One or more system checks failed. ❌❌❌"
    exit 1
fi
