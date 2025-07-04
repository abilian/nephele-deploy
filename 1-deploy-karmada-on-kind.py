"""
Minimal recipe to deploy king kubernetes engine and tools on a ubuntu like distribution.


pyinfra -y -vv --user root HOST deploy-root-kind-k8s.py
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
    create_kind_k8s_test_cluster()
    # install_karmada_cluster_from_sources()


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
        name=f"Install 'non-classic' snap packages",
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


def install_kubectl():
    server.shell(
        name="install kubectl",
        commands=[
            "rm -f /root/kubectl",
            "rm -f /usr/local/bin/kubectl",
            'curl -LO "https://dl.k8s.io/release/$(curl -L -s https://dl.k8s.io/release/stable.txt)/bin/linux/amd64/kubectl"',
            "install -o root -g root -m 0755 kubectl /usr/local/bin/kubectl",
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


def start_services() -> None:
    for service in SERVICES:
        systemd.service(
            name=f"Start&enable service: {service}",
            service=service,
            enabled=True,
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
            f"cd {GITS}/karmada && hack/local-up-karmada.sh",
        ],
    )




# expected result:

# ~# kind get clusters
# karmada-host
# kind
# member1
# member2
# member3

# # export KUBECONFIG="$HOME/.kube/karmada.config"
# # kubectl config use-context karmada-host
#  Switched to context "karmada-host".
#
#
# root@sloop:~# kubectl config view
# apiVersion: v1
# clusters:
# - cluster:
#     certificate-authority-data: DATA+OMITTED
#     server: https://172.18.0.4:5443
#   name: karmada-apiserver
# - cluster:
#     certificate-authority-data: DATA+OMITTED
#     server: https://172.18.0.4:6443
#   name: kind-karmada-host
# contexts:
# - context:
#     cluster: karmada-apiserver
#     user: karmada-apiserver
#   name: karmada-apiserver
# - context:
#     cluster: kind-karmada-host
#     user: kind-karmada-host
#   name: karmada-host
# current-context: karmada-host
# kind: Config
# preferences: {}
# users:
# - name: karmada-apiserver
#   user:
#     client-certificate-data: DATA+OMITTED
#     client-key-data: DATA+OMITTED
# - name: kind-karmada-host
#   user:
#     client-certificate-data: DATA+OMITTED
#     client-key-data: DATA+OMITTED


main()
