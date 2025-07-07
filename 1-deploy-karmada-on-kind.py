"""
Minimal recipe to deploy kind kubernetes engine and tools on a ubuntu like distribution.

pyinfra -y -vv --user root HOST 1-deploy-root-kind-k8s.py
"""

from pyinfra import host
from pyinfra.facts.files import File
from pyinfra.operations import apt, files, git, server, snap, systemd

from common import check_server
from constants import KARMADA_RELEASE_BRANCH

GITS = "/root/git"

APT_PACKAGES = ["curl", "wget", "tar", "gnupg", "vim", "snapd"]
SNAP_PACKAGES = ["lxd"]
SNAP_PACKAGES_CLASSIC = ["helm"]

SERVICES = [
    "containerd",
    "docker",
    # "snap.lxd.activate",
]


def main() -> None:
    check_server()
    install_packages()
    start_services()
    install_kubectl()
    install_kind()
    # create_kind_k8s_test_cluster()
    install_karmada()
    delete_kind_clusters()
    create_kind_karmada_cluster()
    init_karmada_configuration()


def install_packages() -> None:
    """Install base packages"""
    install_apt_packages()
    install_snap_packages()
    install_snap_packages_classic()


def install_apt_packages() -> None:
    apt.packages(
        name="Install base packages",
        packages=APT_PACKAGES,
        update=True,
    )


def install_snap_packages():
    snap.package(
        name="Install 'non-classic' snap packages",
        packages=SNAP_PACKAGES,
    )


def install_snap_packages_classic():
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
            name=f"Start&enable service: {service}",
            service=service,
            enabled=True,
        )


def install_kubectl():
    fact = host.get_fact(File, "/usr/local/bin/kubectl")
    if fact:
        return
    server.shell(
        name="install kubectl",
        commands=[
            'curl -LO "https://dl.k8s.io/release/$(curl -L -s https://dl.k8s.io/release/stable.txt)/bin/linux/amd64/kubectl"',
            "install -o root -g root -m 0755 kubectl /usr/local/bin/kubectl",
            "rm -f /root/kubectl",
        ],
    )


def install_kind():
    fact = host.get_fact(File, "/usr/local/bin/kind")
    if fact:
        return

    server.shell(
        name="Install kind",
        commands=[
            "go install sigs.k8s.io/kind@v0.29.0",
            "cp -f /root/go/bin/kind /usr/local/bin",
        ],
    )


def create_kind_k8s_test_cluster():
    server.shell(
        name="create kind k8s cluster for test",
        commands=[
            "kind delete cluster || true",
            "kind create cluster",
        ],
    )
    server.shell(
        name="show cluster info",
        commands=[
            "kubectl cluster-info --context kind-kind",
        ],
    )
    server.shell(
        name="delete test cluster",
        commands=[
            "kind get clusters| grep '^kind$' && kind delete cluster||true",
        ],
    )


def install_karmada() -> None:
    INSTALLER_URL = "https://raw.githubusercontent.com/karmada-io/karmada/master/hack/install-cli.sh"
    # VERSION='v1.14.1'
    files.file(
        name="Remove old karmada CLI",
        path="/usr/local/bin/kubectl-karmada",
        present=False,
    )
    server.shell(
        name="Install Karmada CLI",
        commands=[
            f"curl -s {INSTALLER_URL} | sudo bash -s kubectl-karmada",
        ],
        _get_pty=True,
    )


def delete_kind_clusters() -> None:
    server.shell(
        name="stop running kind clusters",
        commands="kind get clusters | xargs -I {} kind delete cluster --name {} || true",
    )


def create_kind_karmada_cluster():
    NAME = "karmada-cluster"
    server.shell(
        name=f"create kind cluster {NAME!r}",
        commands=f"kind create cluster -n {NAME}",
    )
    server.shell(
        name="show cluster info",
        commands=[
            # f"kubectl cluster-info --context kind-{NAME}",
            "kubectl cluster-info --kubeconfig ~/.kube/config",
        ],
    )


def init_karmada_configuration():
    VERSION = "v1.14.1"
    CRDS = (
        f"https://github.com/karmada-io/karmada/releases/download/{VERSION}/crds.tar.gz"
    )
    LOG = "/root/log_karmada_init.txt"
    server.shell(
        name="initialize karmada configuration",
        commands=[
            "kubectl karmada deinit",
            "sleep 10",
            f"kubectl karmada --kubeconfig ~/.kube/config init --crds {CRDS}",
            "cp -f /etc/karmada/karmada-apiserver.config ~/.kube/",
        ],
        _get_pty=True,
    )
    server.shell(
        name="show cluster info",
        commands=[
            "kubectl cluster-info --kubeconfig ~/.kube/config",
        ],
    )


main()
