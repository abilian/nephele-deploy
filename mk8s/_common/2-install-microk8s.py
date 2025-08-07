from pyinfra.operations import server

def main():
    server.shell(
        name="Install MicroK8s",
        commands=[
            "snap install microk8s --classic --channel=1.29"
        ]
    )
    server.shell(
        name="Wait for MicroK8s to be ready",
        commands=[
            "microk8s status --wait-ready"
        ]
    )
    server.shell(
        name="Enable MicroK8s addons",
        commands=[
            "microk8s enable dns",
            "microk8s enable hostpath-storage",
            "microk8s enable registry"  # This provides the container registry
        ]
    )
    server.shell(
        name="Alias kubectl and helm",
        commands=[
            "snap alias microk8s.kubectl kubectl",
            "snap alias microk8s.helm3 helm"
        ]
    )
    server.shell(
        name="Write kubeconfig",
        commands=[
            "mkdir -p /root/.kube",
            "microk8s config > /root/.kube/config"
        ]
    )
main()
