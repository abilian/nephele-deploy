"""
Minimal recipe to deploy king kubernetes engine and tools on a ubuntu like distribution.


pyinfra -y -vv --user root HOST deploy-root-kind-k8s.py
"""

from pyinfra import host, logger
from pyinfra.facts.server import LsbRelease
from pyinfra.operations import apt, server, snap, systemd, git

START_SERVICES = [
    "containerd",
    "docker",
    "snap.lxd.activate",
]
GITS = "/root/gits"

APT_PACKAGES = ["curl", "wget", "tar", "gnupg", "vim", "snapd"]
# golang-go breaks
# APT_PACKAGES = ["curl", "wget", "tar", "gnupg", "vim", "snapd", "golang-go"]
SNAP_PACKAGES = ["lxd"]
SNAP_PACKAGES_CLASSIC = ["helm"]


def main() -> None:
    result = None
    result_karmada = None

    check_server()
    install_apt_packages()
    ensure_go_in_root_path()
    install_snap_packages()
    install_snap_packages_classic()
    start_services()
    install_kubectl()
    install_kind()
    create_kind_k8s_test_cluster()
    install_karmada_cluster_from_sources()
    install_cilium()

    if result and result.changed and result.stdout:
        logger.info(
            f"on {host.name}: {' '.join(result.stdout)}\n{' '.join(result.stderr)}"
        )
    if result_karmada and result_karmada.changed and result_karmada.stdout:
        logger.info(f"on {host.name}: {' '.join(result.stdout)}")


def check_server() -> None:
    logger.info("Starting Common Prerequisite Checks")
    lsb_info = host.get_fact(LsbRelease)
    is_apt_based = lsb_info["id"].lower() in ["ubuntu", "debian"]
    assert is_apt_based, (
        f"Unsupported OS: {lsb_info['id']}. This script is designed for Debian/Ubuntu."
    )


def install_apt_packages() -> None:
    apt.packages(
        name="Install base packages",
        packages=APT_PACKAGES,
        update=True,
    )


def ensure_go_in_root_path():
    GOLANG = "go1.24.3.linux-amd64.tar.gz"
    server.shell(
        name="Install go lang",
        commands=[
            f"curl -LO https://go.dev/dl/{GOLANG}",
            "rm -rf /usr/local/go",
            f"tar -C /usr/local -xzf {GOLANG}",
        ],
        _get_pty=True,
    )

    server.shell(
        name="Ensure go in root path",
        commands=["echo 'export PATH=\"/usr/local/go/bin:$PATH\"' >> ~/.bashrc"],
        _get_pty=True,
    )


def install_snap_packages():
    """Install lxd via snap"""
    for package in SNAP_PACKAGES:
        # iter on list because error :
        #  "a single snap name is needed to specify channel flags"
        snap.package(
            name=f"Install snap package {package}",
            packages=package,
            classic=False,
        )


def install_snap_packages_classic():
    """Install microk8s via snap"""
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
        _get_pty=True,
    )


def install_kind():
    server.shell(
        name="Install kind",
        commands=[
            ". /root/.bashrc && go install sigs.k8s.io/kind@v0.29.0",
            "cp -f /root/go/bin/kind /usr/local/bin",
        ],
        _get_pty=True,
    )


def create_kind_k8s_test_cluster():
    server.shell(
        name="create kind k8s cluster for test",
        commands=[
            "kind get clusters| grep '^kind$' && kind delete cluster||true",
            "kind create cluster",
        ],
        _get_pty=True,
    )
    global result
    result = server.shell(
        name="show cluster info",
        commands=[
            "kubectl cluster-info --context kind-kind",
        ],
        _get_pty=True,
    )
    server.shell(
        name="delete test cluster",
        commands=[
            "kind get clusters| grep '^kind$' && kind delete cluster||true",
        ],
        _get_pty=True,
    )


def start_services() -> None:
    for service in START_SERVICES:
        systemd.service(
            name=f"Enable/start {service}",
            service=service,
            running=True,
            enabled=True,
        )


def install_karmada_cluster_from_sources() -> None:
    server.shell(name=f"make {GITS} repository", commands=[f"mkdir -p {GITS}"])

    git.repo(
        name="clone/update karmada source",
        src="https://github.com/karmada-io/karmada.git",
        dest=f"{GITS}/karmada",
        branch="master",
        pull=True,
        rebase=False,
        user="root",
        group="root",
        ssh_keyscan=False,
        update_submodules=False,
        recursive_submodules=False,
    )
    global result_karmada
    result_karmada = server.shell(
        name="setup Karmada",
        commands=[
            f". /root/.bashrc && cd {GITS}/karmada && hack/local-up-karmada.sh",
        ],
        _get_pty=True,
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
