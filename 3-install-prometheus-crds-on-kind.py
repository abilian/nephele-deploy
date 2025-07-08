"""
Minimal recipe to deploy prometheus CRDS on kind on ubuntu server.

pyinfra -y -vv --user root HOST 3-install-prometheus-crds-on-kind.py
"""

import io

from pyinfra.operations import files, server

from common import check_server

NAMESPACE = "monitoring"
# Define the Prometheus Operator version
PROM_OP_VERSION = "v0.78.2"
# Base URL for the Prometheus Operator CRDs
BASE_URL = (
    "https://raw.githubusercontent.com/prometheus-operator/"
    f"prometheus-operator/{PROM_OP_VERSION}/example/prometheus-operator-crd"
)

# Kubeconfig file of the Karmada control plane
KUBECONFIG = "/root/.kube/karmada-apiserver.config"

PARAM_LIST = [
    "monitoring.coreos.com_alertmanagerconfigs.yaml",
    "monitoring.coreos.com_alertmanagers.yaml",
    "monitoring.coreos.com_podmonitors.yaml",
    "monitoring.coreos.com_probes.yaml",
    "monitoring.coreos.com_prometheusagents.yaml",
    "monitoring.coreos.com_prometheuses.yaml",
    "monitoring.coreos.com_prometheusrules.yaml",
    "monitoring.coreos.com_scrapeconfigs.yaml",
    "monitoring.coreos.com_servicemonitors.yaml",
    "monitoring.coreos.com_thanosrulers.yaml",
]


def qualified_name(param: str) -> str:
    dom, suffix = param.split("_")
    name = suffix.split(".")[0]
    return f"{name}.{dom}"


def make_kube_cmd(param: str) -> str:
    """Generate the kubectl command to apply."""
    return (
        f"kubectl apply --server-side -f {BASE_URL}/{param} --kubeconfig {KUBECONFIG}"
    )


def main() -> None:
    check_server()
    apply_crds_parameters()
    # create_monitoring_namespace()
    check_crds_applied()
    show_monitoring_pods()


def apply_crds_parameters() -> None:
    for param in PARAM_LIST:
        command = make_kube_cmd(param)
        server.shell(name=f"Apply kubectl config {param}", commands=command)


def create_monitoring_namespace() -> None:
    server.shell(
        name="Create monitoring namespace",
        commands=[
            f"kubectl create ns {NAMESPACE} --kubeconfig {KUBECONFIG}",
        ],
    )


def show_monitoring_pods() -> None:
    server.shell(
        name=f"Show pods of {NAMESPACE!r}",
        commands=[
            f"kubectl get pods -n {NAMESPACE}",
        ],
    )


def check_crds_applied() -> None:
    for param in PARAM_LIST:
        name = qualified_name(param)
        server.shell(
            name=f"Check crd {name!r}",
            commands=[
                f"kubectl get crd {name} --kubeconfig {KUBECONFIG}",
            ],
        )


main()
