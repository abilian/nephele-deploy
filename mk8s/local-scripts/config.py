import os

# --- Core Versions ---
KARMADA_VERSION = "1.14.2"
KUBE_VERSION_TAG = "v1.31.3"

# --- Cluster & Naming Definitions ---
MEMBER_CLUSTERS = ["member1", "member2", "member3"]
LXD_PROFILE_NAME = "microk8s"
LXD_BRIDGE_NAME = "lxdbr0"

# --- Host & Kubeconfig Paths ---
HOST_KUBECONFIG = "/var/snap/microk8s/current/credentials/client.config"
KARMADA_KUBECONFIG = os.path.expanduser("~/.kube/karmada.config")
HOST_REGISTRY = "localhost:32000"
CONFIG_FILES_DIR = "/root"  # Directory where member configs will be saved

# --- Networking ---
# CORRECTED: Changed port for member3 to avoid conflict with the host's MicroK8s
PORT_MAPPING = {
    "member1": "16441",
    "member2": "16442",
    "member3": "16444",
}
CONTAINER_API_PORT = "16443"

KARMADA_NAMESPACE = "karmada-system"

# --- Image Definitions ---
KARMADA_REPO = "docker.io/karmada"
KARMADA_IMAGES = {
    "karmada-aggregated-apiserver": f"{KARMADA_REPO}/karmada-aggregated-apiserver:v{KARMADA_VERSION}",
    "karmada-controller-manager": f"{KARMADA_REPO}/karmada-controller-manager:v{KARMADA_VERSION}",
    "karmada-scheduler": f"{KARMADA_REPO}/karmada-scheduler:v{KARMADA_VERSION}",
    "karmada-webhook": f"{KARMADA_REPO}/karmada-webhook:v{KARMADA_VERSION}",
    "karmada-agent": f"{KARMADA_REPO}/karmada-agent:v{KARMADA_VERSION}",
}

K8S_REPO = "registry.k8s.io"
K8S_IMAGES = {
    "etcd": f"{K8S_REPO}/etcd:3.5.12-0",
    "kube-apiserver": f"{K8S_REPO}/kube-apiserver:{KUBE_VERSION_TAG}",
    "kube-controller-manager": f"{K8S_REPO}/kube-controller-manager:{KUBE_VERSION_TAG}",
}
