"""
Minimal recipe to remove all services and packages

Warning: connection as user root.

pyinfra -y -vvv --user root HOST deploy-root-clean-all.py
"""

from pyinfra import host, logger
from pyinfra.facts.server import LsbRelease
from pyinfra.operations import apt, server, snap, systemd

SERVICES = [
    "containerd",
    "docker",
    "snap.microk8s.daemon-apiserver-kicker",
    "snap.microk8s.daemon-apiserver-proxy",
    "snap.microk8s.daemon-cluster-agent",
    "snap.microk8s.daemon-containerd",
    "snap.microk8s.daemon-etcd",
    "snap.microk8s.daemon-flanneld",
    "snap.microk8s.daemon-k8s-dqlite",
    "snap.microk8s.daemon-kubelite",
    "snap.prometheus.prometheus",
]
SNAP_PACKAGES = ["microk8s", "helm", "prometheus"]
APT_PACKAGES = ["docker-ce", "docker-ce-cli", "containerd.io"]


def main() -> None:
    check_server()
    # list_services()
    stop_services()
    remove_snap_packages()
    erase_all_docker_contents()
    remove_apt_packages()
    erase_all_karmada_config()
    erase_all_kubernetes_config()


def check_server() -> None:
    logger.info("Starting Common Prerequisite Checks")
    lsb_info = host.get_fact(LsbRelease)
    is_apt_based = lsb_info["id"].lower() in ["ubuntu", "debian"]
    assert is_apt_based, (
        f"Unsupported OS: {lsb_info['id']}. This script is designed for Debian/Ubuntu."
    )


def list_services() -> None:
    server.shell(
        name="List systemd services",
        commands=["systemctl list-unit-files --type=service --state=enabled"],
        _sudo=True,
    )


def stop_services() -> None:
    for service in SERVICES:
        systemd.service(
            name=f"Stop and disable {service}",
            service=service,
            running=False,
            enabled=False,
        )


def remove_snap_packages() -> None:
    for package in SNAP_PACKAGES:
        snap.package(
            name=f"Remove {package}",
            packages=package,
            present=False,
        )


def erase_all_docker_contents() -> None:
    server.shell(
        name="Stop docker containers",
        commands=["docker stop $(docker ps -q) || true"],
    )

    server.shell(
        name="Erase all docker contents",
        commands=["docker system prune -a -f --volumes || true"],
    )


def remove_apt_packages() -> None:
    apt.packages(
        name=f"Remove packages {APT_PACKAGES!r}",
        packages=APT_PACKAGES,
        present=False,
        extra_uninstall_args="--purge --autoremove",
    )


def erase_all_karmada_config() -> None:
    server.shell(
        name="remove /var/lib/karmada-etcd",
        commands=["rm -fr /var/lib/karmada-etcd || true"],
    )

    server.shell(
        name="remove /etc/karmada",
        commands=["rm -fr /etc/karmada || true"],
    )


def erase_all_kubernetes_config() -> None:
    server.shell(
        name="remove /var/lib/kubelet",
        commands=["rm -fr /var/lib/kubelet || true"],
    )

    server.shell(
        name="remove ~/.kube",
        commands=["rm -fr ~/.kube || true"],
    )


main()
