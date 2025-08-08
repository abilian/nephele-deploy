"""
Minimal recipe to merge kube configs.

pyinfra -y -v --user root ${SERVER_NAME} 4-merge-kube-configs.py
"""

from pyinfra.operations import python, server

from common import log_callback


def main() -> None:
    merge_kube_configs()


def merge_kube_configs() -> None:
    server.shell(
        name="Merge kube configs",
        commands=[
            """
            export KUBECONFIG="/root/.kube/karmada.config:/root/.kube/members.config"
            kubectl config view --merge --flatten > /root/.kube/karmada-apiserver.config
            chmod 666 /root/.kube/karmada-apiserver.config
            """
        ],
        _shell_executable="/bin/bash",
    )

    result = server.shell(
        name="kubectl config view",
        commands=[
            """
            kubectl config view --kubeconfig=/root/.kube/karmada-apiserver.config
            """
        ],
        _shell_executable="/bin/bash",
    )

    python.call(
        name="Show config kubectl config view",
        function=log_callback,
        result=result,
    )


main()
