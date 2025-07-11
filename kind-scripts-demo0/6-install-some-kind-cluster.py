"""
Minimal recipe to deploy a kind cluster on ubuntu server.

debug:
cd kind-scripts ; pyinfra -y -vvv --user root "${SERVER_NAME}" 6-install-some-kind-cluster.py

strong debug:
change to the commented line

f"kind create cluster --config /root/{KIND_CONFIG_FILE} -n {CLUSTER_NAME}",
# f"kind create cluster -v 3 --config /root/{KIND_CONFIG_FILE} -n {CLUSTER_NAME} --retain",

then look in debug logs, somewhere like:
cat /tmp/2497512524/bxl-cluster-worker/journal.log
"""

import io

from pyinfra.operations import files, python, server

from common import check_server, log_callback

KUBECONFIG = "/root/.kube/karmada-apiserver.config"
CLUSTER_NAME = "bxl-cluster"
CLUSTER_CTX = f"kind-{CLUSTER_NAME}"

KIND_CONFIG_FILE = "kind-config.yaml"

KIND_CONFIG = f"""\
kind: Cluster
apiVersion: kind.x-k8s.io/v1alpha4
name: {CLUSTER_NAME}
networking:
  podSubnet: "10.100.0.0/16"     # --pod-network-cidr
  serviceSubnet: "10.150.0.0/16" # --service-cidr
  # apiServerAddress: "127.0.0.1" # default
  apiServerPort: 6443
#nodes:
  # one node hosting a control plane
  #- role: control-plane
  #  extraMounts:
  #  - hostPath: /path/to/my/files
  #    containerPath: /files
  #- role: worker
  #- role: worker
nodes:
  - role: control-plane
    extraPortMappings:
      - containerPort: 80
        hostPort: 80
        listenAddress: "127.0.0.1"
      - containerPort: 443
        hostPort: 443
        listenAddress: "127.0.0.1"
  - role: worker
  - role: worker
"""
# spec:
#   containers:
#   - name: foo
#     image: hashicorp/http-echo:0.2.3
#     args:
#     - "-text=foo"
#     ports:
#     - containerPort: 5678
#       hostPort: 80


def main() -> None:
    check_server()
    put_kind_config_file()
    delete_prior_kind_cluster()
    create_kind_cluster()
    show_clusters()


def put_kind_config_file() -> None:
    files.put(
        name=f"Put file {KIND_CONFIG_FILE!r}",
        src=io.StringIO(KIND_CONFIG),
        dest=f"/root/{KIND_CONFIG_FILE}",
    )


def delete_prior_kind_cluster() -> None:
    server.shell(
        name="Delete any prior kind cluster",
        commands=[
            f"kind delete cluster -n {CLUSTER_NAME}",
        ],
        _ignore_errors=True,
    )


def create_kind_cluster() -> None:
    server.shell(
        name=f"Create kindcluster {CLUSTER_NAME} {KIND_CONFIG_FILE} ",
        commands=[
            f"kind create cluster --config /root/{KIND_CONFIG_FILE} -n {CLUSTER_NAME}",
            # debug only: f"kind create cluster -v 3 --config /root/{KIND_CONFIG_FILE} -n {CLUSTER_NAME} --retain",
        ],
    )


def show_clusters() -> None:
    result = server.shell(
        name="Show kind clusters",
        commands=[
            "kind get clusters",
        ],
    )
    python.call(
        name="Show kind clusters",
        function=log_callback,
        result=result,
    )


def show_nodes() -> None:
    result = server.shell(
        name="Show cluster nodes",
        commands=[
            "kubectl get nodes",
        ],
    )
    python.call(
        name="Show cluster nodes",
        function=log_callback,
        result=result,
    )


def show_cluster_info() -> None:
    result = server.shell(
        name=f"Show cluster info {CLUSTER_CTX}",
        commands=[
            f"kubectl cluster-info --context {CLUSTER_CTX}",
        ],
    )
    python.call(
        name=f"Show cluster info {CLUSTER_CTX}",
        function=log_callback,
        result=result,
    )


main()
