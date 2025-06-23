"""
Minimal recipe to deploy
- cleaned mk8s and hdar, no Karmada installation

Warning: connection as user root.

pyinfra -y -vvv --user root HOST setup-mk8s-hello.py
"""

from pyinfra import host
from pyinfra.facts.files import File
from pyinfra.facts.hardware import Ipv4Addrs  # Correct import for Ipv4Addrs
from pyinfra.facts.server import LsbRelease, User
from pyinfra.operations import apt, docker, files, git, server, snap, systemd

from common import check_server
from constants import GITS, HDAR_URL, REGISTRY_PORT

BASE_APT_PACKAGES = [
    "ca-certificates",
    "lsb-release",
    "curl",
    "wget",
    "tar",
    "gnupg",
    "vim",
    "python3-requests",
    "snapd",
]

DOCKER_APT_PACKAGES = [
    "docker-ce",
    "docker-ce-cli",
    "containerd.io",
    # "docker-buildx-plugin",
    # "docker-compose-plugin",
]

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
SMO_H3NI_URL = "https://github.com/abilian/smo-h3ni.git"
SMO_CODE = f"{GITS}/smo-h3ni"
SMO_HELLO_CODE = f"{SMO_CODE}/examples/hello-world-demo"


def main() -> None:
    check_server()
    update_server()
    install_packages()
    # install_go()
    # install_uv()
    install_docker()
    # make_hdarctl()
    start_services()
    reset_mk8s()
    configure_mk8s()
    start_docker_registry()
    make_smo_example_hello_world()


def update_server() -> None:
    apt.update(name="Update apt cache")
    apt.upgrade(name="Upgrade system packages")


def install_packages() -> None:
    install_apt_packages()
    install_mk8s()
    install_mk8s_classic()


def install_apt_packages() -> None:
    apt.packages(
        name="Install base packages",
        packages=BASE_APT_PACKAGES,
        update=True,
    )


def install_mk8s():
    snap.package(
        name="Install (non-classic) snap package",
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


def reset_mk8s() -> None:
    server.shell(
        name="Reset mk8s configuration",
        commands=[
            "microk8s reset",
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


#
# Go
#
def install_go() -> None:
    apt.ppa(
        name="Add the Go ppa",
        src="ppa:longsleep/golang-backports",
    )
    apt.packages(
        name="Install Go packages",
        packages=["golang-go"],
        update=True,
    )


#
# uv
#
def install_uv() -> None:
    fact = host.get_fact(File, "/usr/bin/uv")
    if not fact:
        server.shell(
            name="install uv",
            commands=["curl -LsSf https://astral.sh/uv/install.sh | sh"],
        )
        server.shell(
            name="copy uv to /usr/bin",
            commands=[
                "cp /root/.local/bin/uv /usr/bin/uv",
            ],
        )


#
# Docker
#
def install_docker() -> None:
    apt.key(
        name="Add the Docker apt gpg key",
        src="https://download.docker.com/linux/ubuntu/gpg",
    )

    lsb_info = host.get_fact(LsbRelease)
    distro = lsb_info["id"].lower()
    code_name = lsb_info["codename"]

    apt.repo(
        name="Add Docker repo",
        src=f"deb https://download.docker.com/linux/{distro} {code_name} stable",
    )

    packages = DOCKER_APT_PACKAGES
    apt.packages(
        name="Install Docker packages",
        packages=packages,
        update=True,
    )

    user = host.get_fact(User)
    server.user(
        name=f"give docker group to {user!r}",
        user=user,
        groups=["docker"],
    )


def make_hdarctl():
    git.repo(
        name="clone/update HDAR source",
        src=HDAR_URL,
        dest=f"{GITS}/hdar",
        branch="main",
    )
    workdir = f"{GITS}/hdar/components/hdar-ctl"
    server.shell(
        name="build HDAR",
        commands=[
            f"cd {workdir} && CGO_ENABLED=0 go build -a -installsuffix cgo -o hdarctl .",
            f"{workdir}/hdarctl -h",
            f"cp {workdir}/hdarctl /usr/bin/hdarctl",
        ],
    )


def start_docker_registry() -> None:
    # server.shell(
    #     name="start docker registry",
    #     commands=[
    #         f"docker run -d -p {REGISTRY_PORT}:5000 --restart=always --name registry registry:latest || true"
    #     ],
    # )

    docker.container(
        name="Deploy docker registry",
        container="registry",
        image="registry:latest",
        ports=[f"{REGISTRY_PORT}:5000"],
    )

    # systemd.service(
    #     name="restart docker daemon",
    #     service="docker",
    #     restarted=True,
    # )

    result = server.shell(
        name="check containers",
        commands=["docker container ls -a"],
    )
    print(result)


def make_smo_example_hello_world():
    git.repo(
        name="clone/update smo_h3ni",
        src=SMO_H3NI_URL,
        dest=SMO_CODE,
        branch="h3ni",
    )

    files.line(
        name="Replace IP address in Makefile",
        path=f"{SMO_HELLO_CODE}/Makefile",
        line=r"HOST_IP :=.*",
        replace=f"HOST_IP := {host.get_fact(Ipv4Addrs)['eth0'][0]}",
    )

    server.shell(
        name="build image, push image",
        commands=[f"cd {SMO_HELLO_CODE} && make push-images"],
    )


main()
