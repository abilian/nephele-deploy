"""
Minimal recipe to deploy microk8s on a ubuntu like distribution and activate
helm and prometheus on it.

pyinfra -y -vvv --user USER HOST deploy-mk8s.py
"""

from pyinfra import host, logger
from pyinfra.facts.server import LsbRelease
from pyinfra.operations import apt, server, snap, systemd

START_SERVICES = [
    "containerd",
    "docker",
    "redis-server",
    "snap.lxd.activate",
    "snap.microk8s.daemon-apiserver-kicker",
    "snap.microk8s.daemon-apiserver-proxy",
    "snap.microk8s.daemon-cluster-agent",
    "snap.microk8s.daemon-containerd",
    "snap.microk8s.daemon-etcd",
    "snap.microk8s.daemon-flanneld",
    "snap.microk8s.daemon-k8s-dqlite",
    "snap.microk8s.daemon-kubelite",
]


def main() -> None:
    check_server()
    install_apt_packages()
    install_mk8s()
    start_services()
    show_status()
    dump_mk8s_config()


def check_server() -> None:
    logger.info("Starting Common Prerequisite Checks")
    lsb_info = host.get_fact(LsbRelease)
    is_apt_based = lsb_info["id"].lower() in ["ubuntu", "debian"]
    assert is_apt_based, (
        f"Unsupported OS: {lsb_info['id']}. This script is designed for Debian/Ubuntu."
    )


def install_apt_packages() -> None:
    packages = ["curl", "wget", "tar", "gnupg", "vim", "snapd"]
    apt.packages(
        name="Install base packages",
        packages=packages,
        update=True,
        _sudo=True,
    )


def install_mk8s():
    """Install microk8s via snap"""
    snap.package(
        name="Install snap packages",
        packages=["lxd", "microk8s", "prometheus"],
        classic=True,
        _sudo=True,
    )


def start_services() -> None:
    for service in START_SERVICES:
        systemd.service(
            name=f"enable/start {service}",
            service=service,
            running=True,
            enabled=True,
            _sudo=True,
        )


def show_status():
    server.shell(
        name="Show microk8s status",
        commands=[
            "microk8s status --wait-ready",
        ],
        _sudo=True,
    )


def dump_mk8s_config():
    server.shell(
        name="Dump microk8s config",
        commands=[
            """[ -f  ~/.kube/config ] || {
                mkdir -p ~/.kube/
                sudo microk8s config > ~/.kube/config
            }
            """
        ],
    )


main()
