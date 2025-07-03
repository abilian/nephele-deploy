"""
Minimal recipe to deploy microk8s on a ubuntu like distribution.

Do not install Prometheux now.
Install Helm from snap packages.

Warning: connection as user root.

pyinfra -y -vv --user root HOST 2-deploy-karmada-on-mk8s.py
"""

from pyinfra.operations import apt, files, git, server, snap, systemd

from common import check_server

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
KA_WAIT_TIMEOUT = 900  # 15min


def main() -> None:
    check_server()
    install_packages()
    start_services()
    show_status()

    configure_mk8s()
    # setup_cilium()
    install_karmada_controller()
    setup_karmada_cluster()

    # install_karmada_cluster_from_sources()


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


def configure_mk8s():
    files.directory(
        name="Create .kube directory",
        path="/root/.kube/",
        mode="0700",
    )
    server.shell(
        name="Generate microk8s config",
        commands=[
            "microk8s config > /root/.kube/config",
        ],
    )


def install_karmada_controller() -> None:
    INSTALLER_URL = "https://raw.githubusercontent.com/karmada-io/karmada/master/hack/install-cli.sh"
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


def setup_karmada_cluster() -> None:
    # server.shell(
    #     name="Deinitialize Karmada cluster",
    #     commands=[
    #         "microk8s kubectl karmada deinit",
    #     ],
    # )

    # FIXME: this is not idempotent, it will fail if karmada is already initialized.
    server.shell(
        name="Initialize Karmada cluster",
        commands=[
            "microk8s kubectl karmada init",
        ],
    )
    server.shell(
        name="Wait for Karmada to be ready",
        commands=[
            f"microk8s kubectl wait --for=condition=Ready pods --all -n karmada-system --timeout={KA_WAIT_TIMEOUT}s",
        ],
    )

# def install_karmada_cluster_from_sources() -> None:
#     files.directory(
#         name=f"create {GITS} directory",
#         path=GITS,
#     )
#     git.repo(
#         name="clone/update karmada source",
#         src="https://github.com/karmada-io/karmada.git",
#         dest=f"{GITS}/karmada",
#         branch=KARMADA_RELEASE_BRANCH,
#         user="root",
#         group="root",
#     )
#     server.shell(
#         name="setup Karmada",
#         commands=[
#             # f"cd {GITS}/karmada && hack/local-up-karmada.sh",
#             # Trying something else:
#             f"cd {GITS}/karmada && hack/deploy-karmada.sh ~/.kube/config microk8s local",
#         ],
#     )


main()
