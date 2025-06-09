import io
import tempfile
import uuid

from pyinfra import host, logger
from pyinfra.facts.server import LsbRelease
from pyinfra.operations import apt, files, server, snap, systemd

# --- Configuration Variables (Fetched from inventory or defaults) ---
# CLUSTER_ROLE = host.data.get("cluster_role", "member")
# CLUSTER_NAME = host.data.get("cluster_name", "default-cluster")
# CILIUM_CLUSTER_ID = host.data.get("cluster_id_cilium", 0)
# POD_CIDR = host.data.get("pod_cidr", "10.244.0.0/16")
# SERVICE_CIDR = host.data.get("service_cidr", "10.96.0.0/12")
# LOCAL_KUBECONFIG = host.data.get("local_kubeconfig_path", "~/.kube/config")
#
# # Central Specific
# KARMADA_KUBECONFIG = host.data.get("karmada_kubeconfig_path", "/etc/karmada/karmada-apiserver.config")
# SMO_IP = host.data.get("smo_ip", "127.0.0.1")
# KARMADA_JOIN_CENTRAL_K8S_CLUSTER_NAME = host.data.get("karmada_join_central_k8s_cluster_name", None)
#
# # Member Specific
# CENTRAL_KARMADA_API_SERVER = host.data.get("central_karmada_api_server", "")
# CENTRAL_KARMADA_TOKEN = host.data.get("central_karmada_token", "")
# CENTRAL_KARMADA_CA_HASH = host.data.get("central_karmada_ca_hash", "")
# CENTRAL_PROMETHEUS_IP_AND_PORT = host.data.get("central_prometheus_ip_and_port", "CENTRAL_PROM_IP:30090")
#
# PROMETHEUS_OPERATOR_VERSION = "v0.78.2"

CENTRAL_KARMADA_API_SERVER = ""
CENTRAL_KARMADA_CA_HASH = ""
CENTRAL_KARMADA_TOKEN = ""
CENTRAL_PROMETHEUS_IP_AND_PORT = "CENTRAL_PROM_IP:30090"
CILIUM_CLUSTER_ID = 0
CLUSTER_NAME = "default-cluster"
CLUSTER_ROLE = "member"
KARMADA_JOIN_CENTRAL_K8S_CLUSTER_NAME = "clustername"
KARMADA_KUBECONFIG = "/etc/karmada/karmada-apiserver.config"
LOCAL_KUBECONFIG = "~/.kube/config"
POD_CIDR = "10.244.0.0/16"
PROMETHEUS_OPERATOR_VERSION = "v0.78.2"
SERVICE_CIDR = "10.96.0.0/12"
SMO_IP = "127.0.0.1"


MINIMAL_KARMADA_CONF_YAML = """apiVersion: config.karmada.io/v1alpha1
kind: KarmadaInitConfig
spec:
  karmadaCrds: "https://github.com/karmada-io/karmada/releases/download/v1.13.2/crds.tar.gz"
  etcd:
    local:
      imageRepository: "registry.k8s.io/etcd"
      imageTag: "3.5.13-0"
      initImage:
        imageRepository: "docker.io/library/alpine"
        imageTag: "3.19.1"
  components:
    karmadaAPIServer:
      imageRepository: "registry.k8s.io/kube-apiserver"
      imageTag: "v1.30.0"
    karmadaAggregatedAPIServer:
      imageRepository: "docker.io/karmada/karmada-aggregated-apiserver"
      imageTag: "v1.13.2"
    kubeControllerManager:
      imageRepository: "registry.k8s.io/kube-controller-manager"
      imageTag: "v1.30.0"
    karmadaControllerManager:
      imageRepository: "docker.io/karmada/karmada-controller-manager"
      imageTag: "v1.13.2"
    karmadaScheduler:
      imageRepository: "docker.io/karmada/karmada-scheduler"
      imageTag: "v1.13.2"
    karmadaWebhook:
      imageRepository: "docker.io/karmada/karmada-webhook"
      imageTag: "v1.13.2"
"""

# or kind: InitConfiguration
# or kind: KarmadaInitConfig ?


def main() -> None:
    check_server()
    setup_server()
    install_karmada_helm()
    install_cilium()
    install_prometheus()


def check_server() -> None:
    logger.info(
        f"Starting Common Prerequisite Checks & Setup for {CLUSTER_NAME} ({CLUSTER_ROLE})"
    )
    lsb_info = host.get_fact(LsbRelease)
    is_apt_based = lsb_info["id"].lower() in ["ubuntu", "debian"]
    assert is_apt_based, (
        f"Unsupported OS: {lsb_info['id']}. This script is designed for Debian/Ubuntu."
    )


def setup_server() -> None:
    packages = ["curl", "wget", "tar", "gnupg"]
    apt.packages(
        name="Install base packages",
        packages=packages,
        update=True,
        _sudo=True,
    )


#
# Helm and Karmada Installation
#
def install_karmada_helm():
    # server.shell(
    #     name="Install Helm if not present",
    #     commands=[
    #         "curl https://raw.githubusercontent.com/helm/helm/main/scripts/get-helm-3 | bash",
    #         "helm version",
    #     ],
    # )
    snap.package(
        name="Install Helm via snap",
        packages=["helm"],
        classic=True,
        _sudo=True,
    )

    # systemd.service(
    #     name="Enable/start helm service",
    #     service="helm",
    #     running=True,
    #     enabled=True,
    #     _sudo=True,
    # )

    server.shell(
        name="Install (or reinstall) Karmada CLI",
        commands=[
            "sudo rm -f /usr/local/bin/karmadactl && curl -s https://raw.githubusercontent.com/karmada-io/karmada/master/hack/install-cli.sh | sudo bash",
            "karmadactl version",
        ],
        _get_pty=True,
        _sudo=True,
    )

    server.shell(
        name="copy karmadactl as kubectl-karmada to allow 'kubectl karmada' format of commands",
        commands=[
            "cd /usr/local/bin && cp -f karmadactl kubectl-karmada",
        ],
        _get_pty=True,
        _sudo=True,
    )

    # Karmada setup
    files.directory(
        name="Ensure Karmada config directory exists",
        path="/etc/karmada",
        _sudo=True,
    )

    # # install kubectl-karmada
    # server.shell(
    #     name="Install plugin kubectl-karmada",
    #     commands=[
    #         "curl -s https://raw.githubusercontent.com/karmada-io/karmada/master/hack/install-cli.sh | sudo bash -s kubectl-karmada",
    #     ],
    #     _get_pty=True,
    #     _sudo=True,
    # )

    server.shell(
        name="Remove current karmada config, stop service",
        commands=["yes | sudo microk8s kubectl karmada deinit"],
        _get_pty=True,
    )

    server.shell(
        name="Initialize Karmada config file from local kube config (generated by deploy-mk8s.py)",
        commands=[
            "microk8s kubectl karmada init"
            # This command should take a few minutes and display the following message
        ],
        _get_pty=True,
        _sudo=True,
    )

    # Karmada is installed successfully.

    # Register Kubernetes cluster to Karmada control plane.

    # Register cluster with 'Push' mode

    # Step 1: Use "kubectl karmada join" command to register the cluster to Karmada control plane. --cluster-kubeconfig is kubeconfig of the member cluster.
    # (In karmada)~# MEMBER_CLUSTER_NAME=$(cat ~/.kube/config  | grep current-context | sed 's/: /\n/g'| sed '1d'| tr -d "\"'")
    # (In karmada)~# kubectl karmada --kubeconfig /etc/karmada/karmada-apiserver.config  join ${MEMBER_CLUSTER_NAME} --cluster-kubeconfig=$HOME/.kube/config

    # Step 2: Show members of karmada
    # (In karmada)~# kubectl --kubeconfig /etc/karmada/karmada-apiserver.config get clusters

    # Register cluster with 'Pull' mode

    # Step 1: Create bootstrap token and generate the 'kubectl karmada register' command which will be used later.
    # ~# kubectl karmada token create --print-register-command --kubeconfig=/etc/karmada/karmada-apiserver.config
    # This command will generate a registration command similar to:

    # kubectl karmada register 172.18.0.5:5443 --token t8xfio.640u9gp9obc72v5d --discovery-token-ca-cert-hash sha256:9cfa542ff48f43793d1816b1dd0a78ad574e349d8f6e005e6e32e8ab528e4244

    # Step 2: Use the output from Step 1 to register the cluster to the Karmada control plane.
    # You need to specify the target member cluster by flag '--kubeconfig'
    # ~# kubectl karmada register 172.18.0.5:5443 --token t8xfio.640u9gp9obc72v5d --discovery-token-ca-cert-hash sha256:9cfa542ff48f43793d1816b1dd0a78ad574e349d8f6e005e6e32e8ab528e4244 --kubeconfig=<path-to-member-cluster-kubeconfig>

    # Step 3: Show members of Karmada.
    # ~# kubectl karmada --kubeconfig=/etc/karmada/karmada-apiserver.config get clusters

    # The kubectl karmada register command has several optional parameters for setting the properties of the member cluster. For more details, run:

    # ~# kubectl karmada register --help

    # files.put(
    #     name="Create temporary Karmada config file",
    #     src=io.StringIO(MINIMAL_KARMADA_CONF_YAML),
    #     dest=KARMADA_KUBECONFIG,
    #     _sudo=True,
    # )
    # server.shell(
    #     name="Initialize Karmada config file",
    #     commands=[
    #         f"karmadactl init --config {KARMADA_KUBECONFIG}",
    #         # f"karmadactl init --kubeconfig {KARMADA_KUBECONFIG}",
    #     ],
    #     _sudo=True,
    # )

    # server.shell(
    #     name="Initialize Karmada control plane if not already initialized",
    #     commands=[
    #         f"""test -f {KARMADA_KUBECONFIG} || {{
    #         echo "{MINIMAL_KARMADA_CONF_YAML}" | sudo tee {KARMADA_KUBECONFIG} > /dev/null
    #         sudo karmadactl init --config {KARMADA_KUBECONFIG}
    #     }}
    #     """
    #     ],
    # )

    # server.shell(
    #     name=f"Join K8s cluster '{KARMADA_JOIN_CENTRAL_K8S_CLUSTER_NAME}' to Karmada",
    #     commands=[
    #         f"sudo karmadactl --kubeconfig {KARMADA_KUBECONFIG} join {KARMADA_JOIN_CENTRAL_K8S_CLUSTER_NAME} --cluster-kubeconfig={LOCAL_KUBECONFIG}"
    #     ],
    # )

    server.shell(
        name="Display current Karmada clusters (for verification)",
        commands=[
            f"sudo microk8s kubectl get clusters --kubeconfig {LOCAL_KUBECONFIG} || true"
        ],
        # this seems to fail
        # use sudo in command to keep HOME
        _get_pty=True,
    )

    server.shell(
        name="Generate Karmada join token command (for member clusters - copy this output)",
        commands=[
            f"sudo microk8s kubectl karmada token create --ttl 0 --print-register-command --kubeconfig {LOCAL_KUBECONFIG}"
        ],
        # use sudo in command to keep HOME
        _get_pty=True,
    )


#     logger.info("IMPORTANT: Copy the above 'karmadactl register ...' command parts for member cluster setup.")
#
#     user_home_fact_op = host.run_shell_command("echo $HOME", sudo=False, ignore_errors=True)
#     user_home_fact = user_home_fact_op.stdout.strip() if user_home_fact_op.stdout else None
#
#     if user_home_fact and host.connection_user:  # host.connection_user might not be set for all connectors
#         dest_kubeconfig_path = f"{user_home_fact}/.kube/karmada-apiserver.config"
#         # Ensure .kube dir exists and is owned by connecting user
#         files.directory(
#             name=f"Ensure .kube directory exists for user {host.connection_user}",
#             path=f"{user_home_fact}/.kube",
#             present=True,
#             mode="700",
#             user=host.connection_user,
#             group=host.connection_user,  # Provide group explicitly
#             sudo=True  # To create/chown dir even if parent needs root, or to chown if already exists as root
#         )
#         server.shell(
#             name="Copy Karmada kubeconfig to user's .kube directory",
#             # cp as root, then chown to the connecting user
#             commands=[
#                 f"cp {KARMADA_KUBECONFIG} {dest_kubeconfig_path} && chown {host.connection_user}:{host.connection_user} {dest_kubeconfig_path}"],
#             sudo=True,
#         )
#     else:
#         logger.warning(
#             "Could not determine user home directory or connection_user to copy Karmada kubeconfig. Please copy manually if needed.")


#
# Cilium Installation
#
CILIUM_INSTALL_SCRIPT = """
CILIUM_CLI_VERSION=$(curl -s https://raw.githubusercontent.com/cilium/cilium-cli/main/stable.txt)
CLI_ARCH=amd64
if [ "$(uname -m)" = "aarch64" ]; then CLI_ARCH=arm64; fi
if [ ! -f /usr/local/bin/cilium ]; then
    echo "Attempting to download Cilium CLI version ${CILIUM_CLI_VERSION} for ${CLI_ARCH}..."
    curl -L --fail --remote-name-all https://github.com/cilium/cilium-cli/releases/download/${CILIUM_CLI_VERSION}/cilium-linux-${CLI_ARCH}.tar.gz{,.sha256sum} && \
    sha256sum --check cilium-linux-${CLI_ARCH}.tar.gz.sha256sum && \
    sudo tar xzvfC cilium-linux-${CLI_ARCH}.tar.gz /usr/local/bin && \
    rm cilium-linux-${CLI_ARCH}.tar.gz{,.sha256sum} && \
    echo "Cilium CLI installed successfully." || (echo "Cilium CLI installation failed." && exit 1)
else
    echo "Cilium CLI already installed."
fi
"""

CILIUM_VALUES = f"""
cluster:
    name: {CLUSTER_NAME}
    id: {CILIUM_CLUSTER_ID}
ipam:
    mode: cluster-pool
    operator:
        clusterPoolIPv4PodCIDRList:
        - {POD_CIDR}
ipv4:
  enabled: true
"""


def install_cilium() -> None:
    print(f"Starting Cilium Installation for {CLUSTER_NAME} ({CLUSTER_ROLE})")
    server.shell(
        name="Install Cilium CLI if not present",
        commands=[CILIUM_INSTALL_SCRIPT],
        _get_pty=True,
        _sudo=True,
    )

    files.put(
        name="Create cilium-values.yaml",
        src=io.StringIO(CILIUM_VALUES),
        dest="/tmp/cilium-values.yaml",
        # _get_pty=True,
        _sudo=True,
    )

    server.shell(
        name="Install Cilium CNI via cilium-cli (WIP)",
        # commands=["sudo cilium install --values /tmp/cilium-values.yaml"],
        commands=["sudo cilium install"],
        _get_pty=True,
        # _sudo=True,
    )

    server.shell(
        name="Enable Cilium Clustermesh",
        commands=["cilium clustermesh enable --service-type=NodePort"],
        _get_pty=True,
        _sudo=True,
    )


#
# logger.info(f"Starting Kube Prometheus Stack Setup for {CLUSTER_NAME} ({CLUSTER_ROLE})")

prometheus_values_content = f"""
prometheus:
  prometheusSpec:
    enableRemoteWriteReceiver: true
    scrapeInterval: 30s
    evaluationInterval: 30s
    externalLabels:
      cluster: {CLUSTER_NAME}
  service:
    nodePort: 30090
    type: NodePort
defaultRules:
  create: false
alertmanager:
  service:
    nodePort: 30093
    type: NodePort
  config:
    global:
      resolve_timeout: 5m
    receivers:
      - name: 'webhook-receiver'
        webhook_configs:
          - url: 'http://{SMO_IP}:8000/alerts'
            send_resolved: false
    route:
      group_by: ['job']
      group_wait: 10s
      group_interval: 1m
      receiver: 'webhook-receiver'
      repeat_interval: 1m
      routes:
        - receiver: "webhook-receiver"
"""
# else:  # member cluster

#     prometheus_values_content = f"""
# prometheus:
#   prometheusSpec:
#     externalLabels:
#       source: {CLUSTER_NAME}
#     scrapeInterval: 30s
#     remoteWrite:
#       - url: "http://{CENTRAL_PROMETHEUS_IP_AND_PORT}/api/v1/write"
#   service:
#     type: NodePort
#     nodePort: 30090
# """


def install_prometheus() -> None:
    logger.info(
        f"Starting Kube Prometheus Stack Setup for {CLUSTER_NAME} ({CLUSTER_ROLE})"
    )

    files.put(
        name="Create prom-values.yaml",
        src=io.StringIO(prometheus_values_content),
        dest="/tmp/prom-values.yaml",
        _get_pty=True,
        _sudo=True,
    )

    server.shell(
        name="Add Prometheus Community Helm repo if not added",
        commands=[
            "helm repo list | grep -q prometheus-community || helm repo add prometheus-community https://prometheus-community.github.io/helm-charts",
            "helm repo update",
        ],
        _get_pty=True,
        _sudo=True,
    )

    server.shell(
        name="Install/Upgrade Kube Prometheus Stack via Helm",
        commands=[
            "helm upgrade --install prometheus --create-namespace -n monitoring prometheus-community/kube-prometheus-stack --values /tmp/prom-values.yaml"
        ],
        _get_pty=True,
        _sudo=True,
    )
    logger.info(f"Kube Prometheus Stack installed/upgraded on {CLUSTER_NAME}.")

    systemd.service(
        name="Enable/start Prometheus service",
        service="snap.prometheus.prometheus",
        running=True,
        enabled=True,
        _sudo=True,
    )


# if CLUSTER_ROLE == "central":
#     logger.info(f"Starting Karmada Service Monitor CRDs Setup (Central Cluster: {CLUSTER_NAME})")
#
#     karmada_crd_base_url = f"https://raw.githubusercontent.com/prometheus-operator/prometheus-operator/{PROMETHEUS_OPERATOR_VERSION}/example/prometheus-operator-crd"
#     karmada_crd_files = [
#         "monitoring.coreos.com_alertmanagerconfigs.yaml", "monitoring.coreos.com_alertmanagers.yaml",
#         "monitoring.coreos.com_podmonitors.yaml", "monitoring.coreos.com_probes.yaml",
#         "monitoring.coreos.com_prometheusagents.yaml", "monitoring.coreos.com_prometheuses.yaml",
#         "monitoring.coreos.com_prometheusrules.yaml", "monitoring.coreos.com_scrapeconfigs.yaml",
#         "monitoring.coreos.com_servicemonitors.yaml", "monitoring.coreos.com_thanosrulers.yaml",
#     ]
#     for crd_file in karmada_crd_files:
#         server.shell(
#             name=f"Apply Karmada CRD: {crd_file}",
#             commands=[
#                 f"kubectl apply --server-side -f {karmada_crd_base_url}/{crd_file} --kubeconfig {KARMADA_KUBECONFIG}"],
#             sudo=False,
#         )
#
#     server.shell(
#         name="Create 'monitoring' namespace in Karmada control plane if not exists",
#         commands=[f"sudo kubectl create ns monitoring --kubeconfig {KARMADA_KUBECONFIG} || true"],
#     )
#
# logger.info(f"Starting Metrics Server Installation for {CLUSTER_NAME} ({CLUSTER_ROLE})")
# metrics_server_components_url = "https://github.com/kubernetes-sigs/metrics-server/releases/latest/download/components.yaml"
# metrics_server_local_yaml = "/tmp/metrics-server-components.yaml"
#
# files.download(
#     name="Download Metrics Server components.yaml",
#     src=metrics_server_components_url,
#     dest=metrics_server_local_yaml,
#     sudo=False,
# )
#
# server.shell(
#     name="Modify Metrics Server YAML to add --kubelet-insecure-tls",
#     commands=[
#         f"grep -q -- '--kubelet-insecure-tls' {metrics_server_local_yaml} || sed -i '/- args:/a \\        - --kubelet-insecure-tls' {metrics_server_local_yaml}"],
#     sudo=False,
# )
#
# server.shell(
#     name="Apply Metrics Server components",
#     commands=[f"kubectl apply -f {metrics_server_local_yaml}"],
#     sudo=False,
# )
# logger.info(f"Metrics Server installed/configured on {CLUSTER_NAME}.")
#
# if CLUSTER_ROLE == "member":
#     logger.info(f"Starting Karmada Join for Member Cluster: {CLUSTER_NAME}")
#
#     if not all([CENTRAL_KARMADA_API_SERVER, CENTRAL_KARMADA_TOKEN, CENTRAL_KARMADA_CA_HASH]):
#         logger.error(f"CRITICAL: Karmada join parameters missing for {CLUSTER_NAME}. Skipping join.")
#     else:
#         check_and_install_tool(
#             "karmadactl",
#             "curl -s https://raw.githubusercontent.com/karmada-io/karmada/master/hack/install-cli.sh | sudo bash",
#             # install_command contains sudo
#             "/usr/local/bin/karmadactl version",
#             needs_sudo_to_install=False  # Command string itself uses sudo
#         )
#
#         karmada_register_command = (
#             f"sudo karmadactl register {CENTRAL_KARMADA_API_SERVER} "
#             f"--token {CENTRAL_KARMADA_TOKEN} "
#             f"--discovery-token-ca-cert-hash {CENTRAL_KARMADA_CA_HASH} "
#             f"--cluster-name {CLUSTER_NAME} "
#             f"--kubeconfig={LOCAL_KUBECONFIG}"
#         )
#         server.shell(
#             name=f"Join member cluster {CLUSTER_NAME} to Karmada",
#             commands=[karmada_register_command],
#         )
#         logger.info(f"Member cluster {CLUSTER_NAME} attempted to join Karmada.")
#
# logger.info(f"Nephele platform setup process for {CLUSTER_NAME} ({CLUSTER_ROLE}) completed its PyInfra steps.")


main()
