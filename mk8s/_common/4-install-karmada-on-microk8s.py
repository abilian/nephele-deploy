from pyinfra.operations import server

from constants import GITS


def main():
    # Install karmadactl
    server.shell(
        name="Install Karmada CLI tools",
        commands=[
            f"cd {GITS}/karmada && hack/install-cli.sh"
        ]
    )
    # Initialize Karmada on the MicroK8s cluster
    server.shell(
        name="Initialize Karmada on MicroK8s",
        commands=[
            "karmadactl init --kubeconfig /root/.kube/config"
        ]
    )
    # Join the MicroK8s cluster to its own Karmada control plane
    server.shell(
        name="Join MicroK8s cluster to itself",
        commands=[
            "karmadactl join member1 --cluster-kubeconfig /root/.kube/config"
        ]
    )
main()
