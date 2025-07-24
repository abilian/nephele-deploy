"""
Minimal recipe to deploy kind kubernetes engine and tools on a ubuntu like distribution.

Creates a KinD cluster with 1 control plane and 2 worker nodes, with limited NodePort mapping.

assuming 0-setup-server.py has already been applied for base packages.

pyinfra -y -vv --user root ${SERVER_NAME} 3-create-kind-cluster.py
"""

from pyinfra import host
from pyinfra.facts.files import File
from pyinfra.operations import apt, files, python, server, snap, systemd
import io
from common import log_callback

# KIND_CONF = """\
# kind: Cluster
# apiVersion: kind.x-k8s.io/v1alpha4
# name: host
# nodes:
# - role: control-plane
# - role: worker
# - role: worker
# - role: worker
# # containerdConfigPatches:
# # - |-
# #   [plugins."io.containerd.grpc.v1.cri".registry.mirrors."localhost:5000"]
# #     endpoint = ["http://registry:5000"]
# networking:
#   apiServerAddress: "0.0.0.0"
# """

HOST_CONFIG_FILENAME = "host.kubeconfig"
KUBE_CONF_DIR = "/root/.kube"
KUBE_CONF_PATH = f"{KUBE_CONF_DIR}/config"
HOST_CONF_PATH = f"{KUBE_CONF_DIR}/{HOST_CONFIG_FILENAME}"
KUBECONFIG = HOST_CONF_PATH


KIND_CONF = f"""\
kind: Cluster
apiVersion: kind.x-k8s.io/v1alpha4
name: host
nodes:
- role: control-plane
  kubeadmConfigPatches:
  - |
    kind: InitConfiguration
    nodeRegistration:
      kubeletExtraArgs:
        node-labels: "ingress-ready=true"
  - |
    kind: ClusterConfiguration
    apiVersion: kubeadm.k8s.io/v1beta3
    apiServer:
      extraArgs:
        service-node-port-range: "30000-32500"
  extraPortMappings:
  - containerPort: 80
    hostPort: 80
    listenAddress: "0.0.0.0" # Use 0.0.0.0 if you need access from other machines on your network
    protocol: tcp
  - containerPort: 443
    hostPort: 443
    listenAddress: "0.0.0.0"
    protocol: tcp
%s
- role: worker
- role: worker
"""


def _make_port_mapping() -> str:
    strings = []
    for port in range(30000, 30501):  # Maps 100 ports from 30000 to 30099
        strings.append(
            (
                f"  - containerPort: {port}\n"
                f"    hostPort: {port}\n"
                '    listenAddress: "127.0.0.1"\n'
                "    protocol: tcp\n"
            )
        )
    return "".join(strings)


def main() -> None:
    delete_kind_clusters()
    create_kind_cluster()


def delete_kind_clusters() -> None:
    server.shell(
        name="Stop running kind clusters",
        commands="kind get clusters | xargs -I {} kind delete cluster --name {} || true",
    )

    result = server.shell(
        name="Get kind clusters (no cluster expected)",
        commands=[
            # f"kubectl cluster-info --context kind-{NAME}",
            "kind get clusters",
        ],
    )
    python.call(
        name="Show kind clusters (no cluster expected)",
        function=log_callback,
        result=result,
    )


def create_kind_cluster():
    root_host_conf = f"/root/{HOST_CONFIG_FILENAME}"
    mapping = _make_port_mapping()
    config = KIND_CONF % mapping

    files.put(
        name=f"Put file {root_host_conf!r}",
        src=io.StringIO(config),
        dest=root_host_conf,
    )
    server.shell(
        name="Create kind cluster",
        commands=[
            f"kind create cluster --name host --config {root_host_conf}",
            "kind export kubeconfig --name host",
            f"cp -f {KUBE_CONF_PATH} {HOST_CONF_PATH}",
        ],
        _get_pty=True,
    )

    result = server.shell(
        name="Get kind cluster",
        commands=[
            # f"kubectl cluster-info --context kind-{NAME}",
            "kind get clusters",
        ],
    )
    python.call(
        name="Show kind cluster",
        function=log_callback,
        result=result,
    )

    result = server.shell(
        name="Get kind cluster 2",
        commands=[
            # f"kubectl cluster-info --context kind-{NAME}",
            f"kubectl --kubeconfig {HOST_CONF_PATH} get nodes --context kind-host",
        ],
    )
    python.call(
        name="Show kind cluster 2",
        function=log_callback,
        result=result,
    )


main()
