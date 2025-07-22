"""
Minimal recipe to deploy kind kubernetes engine and tools on a ubuntu like distribution.

assuming 0-setup-server.py has already been applied for base packages.

pyinfra -y -vv --user root ${SERVER_NAME} 2-install-kind-kubectl.py
"""

from pyinfra import host
from pyinfra.facts.files import File
from pyinfra.operations import apt, files, python, server, snap, systemd

# python.call(name=" ", function=log_callback, result=result)

APT_PACKAGES = ["snapd"]
SNAP_PACKAGES = ["lxd"]
SNAP_PACKAGES_CLASSIC = ["helm", "kubeadm"]

SERVICES = [
    "containerd",
    "docker",
    # "snap.lxd.activate",
]


def main() -> None:
    install_packages()
    start_services()
    install_kubectl()
    install_kind()


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
            name=f"Install snap package {package!r}",
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
    VERSION = "v0.29.0"
    server.shell(
        name="Install kind",
        commands=[
            f"go install sigs.k8s.io/kind@{VERSION}",
            "cp -f /root/go/bin/kind /usr/local/bin",
        ],
    )


main()
