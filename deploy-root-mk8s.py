"""
Minimal recipe to deploy microk8s on a ubuntu like distribution.

Do not install Prometheux now.
Install Helm from snap packages.

Warning: connection as user root.

pyinfra -y -vv --user root HOST deploy-root-mk8s.py
"""

from pyinfra import host, logger
from pyinfra.facts.server import LsbRelease
from pyinfra.operations import apt, server, snap, systemd

APT_PACKAGES = ["curl", "wget", "tar", "gnupg", "vim", "snapd"]

SERVICES = [
    "containerd",
    "docker",
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

SNAP_PACKAGES = ["lxd"]
SNAP_PACKAGES_CLASSIC = ["microk8s", "helm"]


def main() -> None:
    check_server()
    install_packages()
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


def install_packages() -> None:
    install_apt_packages()
    install_mk8s()
    install_mk8s_classic()


def install_apt_packages() -> None:
    apt.packages(
        name="Install base packages",
        packages=APT_PACKAGES,
        update=True,
    )


def install_mk8s():
    snap.package(
        name=f"Install (non-classic) snap package",
        packages=SNAP_PACKAGES,
    )


def install_mk8s_classic():
    """Install microk8s via snap"""
    for package in SNAP_PACKAGES_CLASSIC:
        # iter on list because error :
        #  "a single snap name is needed to specify channel flags"
        snap.package(
            name=f"Install snap package {package}",
            packages=package,
            classic=True,
        )


def start_services() -> None:
    for service in SERVICES:
        systemd.service(
            name=f"Start and enable service: {service}",
            service=service,
            enabled=True,
        )


def show_status():
    server.shell(
        name="Show microk8s status",
        commands=[
            "microk8s status --wait-ready",
        ],
    )


def dump_mk8s_config():
    server.shell(
        name="Dump microk8s config",
        commands=[
            "[ -f  ~/.kube/config ] || mkdir -p ~/.kube/",
            "microk8s config > ~/.kube/config",
        ],
    )


main()
