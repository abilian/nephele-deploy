"""
Minimal recipe to deploy Metrics Server on kind on ubuntu server.

pyinfra -y -vv --user root HOST 4-install-metrics-server-kind.py
"""

from pyinfra.operations import python, server

from common import check_server, log_callback


KUBECONFIG = "/root/.kube/karmada-apiserver.config"


def main() -> None:
    check_server()
    install_metrics_server()
    display_all_crds()


def install_metrics_server() -> None:
    COMPONENT_SOURCE = (
        "https://github.com/kubernetes-sigs/metrics-server/"
        "releases/latest/download/components.yaml"
    )
    server.shell(
        name="Install Metrics Server",
        commands=[
            f"wget {COMPONENT_SOURCE}",
            "sed -i '/- args:/a \        - --kubelet-insecure-tls' components.yaml",
            f"kubectl apply -f components.yaml --kubeconfig {KUBECONFIG}",
            f"kubectl get crds --kubeconfig {KUBECONFIG}",
        ],
    )


def display_all_crds() -> None:
    result = server.shell(
        name="Display all crds",
        commands=[f"kubectl get crds --kubeconfig {KUBECONFIG}"],
    )
    python.call(
        name="Display all crds",
        function=log_callback,
        result=result,
    )


main()
