"""
Minimal recipe to deploy
- full docker dependencies and registry

Warning: connection as user root.

pyinfra -y -vvv --user root HOST 0-setup-server.py
"""

from pyinfra import host
from pyinfra.facts.files import File
from pyinfra.facts.server import LsbRelease, User
from pyinfra.operations import apt, docker, git, server

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
]

DOCKER_APT_PACKAGES = [
    "docker-ce",
    "docker-ce-cli",
    "containerd.io",
    # "docker-buildx-plugin",
    # "docker-compose-plugin",
]


def main() -> None:
    check_server()
    update_server()
    setup_server()
    install_go()
    install_uv()
    install_docker()
    make_hdarctl()
    start_docker_registry()


def update_server() -> None:
    apt.update(name="Update apt cache")
    apt.upgrade(name="Upgrade system packages")


def setup_server() -> None:
    packages = BASE_APT_PACKAGES
    apt.packages(
        name="Install base packages",
        packages=packages,
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


main()
