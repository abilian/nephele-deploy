from pyinfra import host
from pyinfra.facts.files import File
from pyinfra.operations import server


def main():
    # Install karmadactl
    fact = host.get_fact(File, "/usr/local/bin/kubectl-karmada")
    if not fact:
        server.shell(
            name="Install Karmada CLI tools",
            commands=[
                "curl -s https://raw.githubusercontent.com/karmada-io/karmada/master/hack/install-cli.sh | bash",
                "cp -f /usr/local/bin/karmadactl /usr/local/bin/kubectl-karmada"
            ],
            _get_pty=True,
        )

    # server.shell(
    #     name="Install Karmada CLI tools",
    #     commands=[
    #         # f"cd {GITS}/karmada && hack/install-cli.sh"
    #         "kubectl karmada init",
    #     ],
    #     _get_pty = True,
    # )

    # Initialize Karmada on the MicroK8s cluster
    server.shell(
        name="Initialize Karmada on MicroK8s",
        commands=[
            "kubectl karmada init --kubeconfig /root/.kube/config"
        ]
    )

    # Join the MicroK8s cluster to its own Karmada control plane
    server.shell(
        name="Join MicroK8s cluster to itself",
        commands=[
            "kubectl karmada join member1 --cluster-kubeconfig /root/.kube/config"
        ]
    )


main()
