"""
Minimal recipe to deploy microk8s on a ubuntu like distribution.

Do not install Prometheux now.
Install Helm from snap packages.

Warning: connection as user root.

pyinfra -y -vv --user root HOST deploy-root-mk8s.py
"""

from pyinfra import host, logger
from pyinfra.facts.server import LsbRelease
from pyinfra.operations import apt, server, snap, systemd, files, git

from common import check_server
from constants import GITS, KARMADA_RELEASE_BRANCH

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
    install_karmada_cluster_from_sources()
    install_cilium()


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
            name=f"Install classic snap package {package}",
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
        name="Wait for microk8s to be ready",
        commands=[
            "microk8s status --wait-ready",
        ],
    )


def dump_mk8s_config():
    files.directory(
        name="Create .kube directory",
        path="/root/.kube/",
        mode="0700",
    )
    server.shell(
        name="Dump microk8s config",
        commands=[
            "microk8s config > /root/.kube/config",
        ],
    )


def install_karmada_cluster_from_sources() -> None:
    files.directory(
        name=f"create {GITS} directory",
        path=GITS,
    )
    git.repo(
        name="clone/update karmada source",
        src="https://github.com/karmada-io/karmada.git",
        dest=f"{GITS}/karmada",
        branch=KARMADA_RELEASE_BRANCH,
        user="root",
        group="root",
    )
    server.shell(
        name="setup Karmada",
        commands=[
            # f"cd {GITS}/karmada && hack/local-up-karmada.sh",
            # Trying something else:
            f"cd {GITS}/karmada && hack/deploy-karmada.sh ~/.kube/config microk8s local",
        ],
    )


def install_cilium() -> None:
    CILIUM_CLI_VERSION = "v0.18.3"
    CLI_ARCH = "amd64"
    FILE = f"cilium-linux-{CLI_ARCH}.tar.gz"
    server.shell(
        name="install Cilium",
        commands=[
            "rm -f /usr/local/bin/cilium",
            f"curl -LO https://github.com/cilium/cilium-cli/releases/download/{CILIUM_CLI_VERSION}/{FILE}",
            f"curl -LO https://github.com/cilium/cilium-cli/releases/download/{CILIUM_CLI_VERSION}/{FILE}.sha256sum",
            f"sha256sum --check {FILE}.sha256sum",
            f"tar xzvfC cilium-linux-{CLI_ARCH}.tar.gz /usr/local/bin",
            f"rm -f {FILE}",
            f"rm -f {FILE}.sha256sum",
        ],
        _get_pty=True,
    )


main()
