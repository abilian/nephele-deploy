"""
Minimal recipe to deploy Metrics Server on kind on ubuntu server.

pyinfra -y -vv --user root ${SERVER_NAME} 7-install-metrics-server.py
"""

from pyinfra.operations import python, server

from common import log_callback

KUBECONFIG = "/root/.kube/config"


def main() -> None:
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
