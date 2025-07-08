"""
Minimal recipe to deploy Metrics Server on kind on ubuntu server.

pyinfra -y -vv --user root HOST 6-install-some-kind-cluster.py
"""

import io
from pyinfra.operations import files, server

from common import check_server

KUBECONFIG = "/root/.kube/karmada-apiserver.config"
CLUSTER_NAME = "test-cluster"
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
        name="create kind cluster",
        commands=[
            f"kind delete cluster -n {CLUSTER_NAME}",
        ],
        _ignore_errors=True,
    )


def create_kind_cluster() -> None:
    server.shell(
        name="create kind cluster",
        commands=[
            f"kind create cluster --config /root/{KIND_CONFIG_FILE} -n {CLUSTER_NAME}",
        ],
    )


def show_clusters() -> None:
    server.shell(
        name="show kind clusters",
        commands=[
            "kind get clusters",
        ],
    )


main()
