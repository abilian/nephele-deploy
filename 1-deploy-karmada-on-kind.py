"""
Minimal recipe to deploy kind kubernetes engine and tools on a ubuntu like distribution.

pyinfra -y -vv --user root HOST 1-deploy-root-kind-k8s.py
"""

from pyinfra import host
from pyinfra.facts.files import File
from pyinfra.operations import apt, files, server, snap, systemd

from common import check_server

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
            name=f"Start & enable service: {service}",
            service=service,
            enabled=True,
        )


def install_kubectl():
    fact = host.get_fact(File, "/usr/local/bin/kubectl")
    if fact:
        return
    server.shell(
        name="Install kubectl",
        commands=[
            (
                "KV=$(curl -L -s https://dl.k8s.io/release/stable.txt); "
                'curl -LO "https://dl.k8s.io/release/${KV}/bin/linux/amd64/kubectl"'
            ),
            "install -o root -g root -m 0755 kubectl /usr/local/bin/kubectl",
            "rm -f /root/kubectl",
        ],
    )


def install_kind():
    """Install kind.

    Documentation: https://kind.sigs.k8s.io/docs/user/quick-start/
    """
    fact = host.get_fact(File, "/usr/local/bin/kind")
    if fact:
        return
    VERSION = "v0.29.0"
    server.shell(
        name="Install kind",
        commands=[
            f"go install sigs.k8s.io/kind@{VERSION}",
            "cp -f /root/go/bin/kind /usr/local/bin",
        ],
    )


def create_kind_k8s_test_cluster():
    server.shell(
        name="Create kind k8s cluster for test",
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
        name="Stop running kind clusters",
        commands="kind get clusters | xargs -I {} kind delete cluster --name {} || true",
    )


def create_kind_karmada_cluster():
    NAME = "karmada-cluster"
    server.shell(
        name=f"Create kind cluster with name {NAME!r}",
        commands=f"kind create cluster -n {NAME}",
    )
    server.shell(
        name="Show cluster info",
        commands=[
            # f"kubectl cluster-info --context kind-{NAME}",
            "kubectl cluster-info --kubeconfig ~/.kube/config",
        ],
    )
    server.shell(
        name="Wait status ready",
        commands=[
            "kubectl wait --for=condition=Ready pods --all -n kube-system --timeout=300s"
        ],
    )


def init_karmada_configuration():
    VERSION = "v1.14.1"
    CRDS = (
        f"https://github.com/karmada-io/karmada/releases/download/{VERSION}/crds.tar.gz"
    )
    LOG = "/root/log_karmada_init.txt"
    RETRY = 24  # 2 min
    WAIT = 5
    server.shell(
        name="Remove old karmada configuration",
        commands="kubectl karmada deinit --purge-namespace || true",
        # "rm -fr /var/lib/karmada-etcd ",
    )
    server.shell(
        name="Install karmada configuration",
        commands=[
            f"""
            echo "" > {LOG}
            count=0
            until grep -q 'installed successfully' {LOG} || [ "$count" -ge "{RETRY}" ]
            do
                sleep {WAIT}
                kubectl karmada --kubeconfig ~/.kube/config init --wait-component-ready-timeout 60 --crds {CRDS} 2>&1 | tee {LOG}
                count=$((count + 1))
                echo "-- try loop number: $count"
            done
            """,
            f"grep -q 'installed successfully' {LOG}",
            "cp -f /etc/karmada/karmada-apiserver.config ~/.kube/",
        ],
        _get_pty=True,
    )
    server.shell(
        name="Show cluster info",
        commands=[
            "kubectl cluster-info --kubeconfig ~/.kube/config",
        ],
    )
    server.shell(
        name="Show pods of karmada-system",
        commands=[
            "kubectl get pods -n karmada-system",
        ],
    )


main()
