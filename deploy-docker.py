"""
Minimal recipe to deploy
- full docker dependencies and registry

pyinfra -y -vvv --user USER HOST deploy-docker.py
"""

from pyinfra import host, logger
from pyinfra.facts.server import Arch, LsbRelease, User
from pyinfra.operations import apt, server, systemd

REGISTRY_PORT = 5000


def main() -> None:
    check_server()
    setup_server()
    install_docker()
    docker_group()
    start_docker_registry()


def check_server() -> None:
    logger.info("Starting Common Prerequisite Checks")
    lsb_info = host.get_fact(LsbRelease)
    is_apt_based = lsb_info["id"].lower() in ["ubuntu", "debian"]
    assert is_apt_based, (
        f"Unsupported OS: {lsb_info['id']}. This script is designed for Debian/Ubuntu."
    )


def setup_server() -> None:
    packages = ["ca-certificates", "lsb-release", "curl", "wget", "tar", "gnupg", "vim"]
    apt.packages(
        name="Install base packages",
        packages=packages,
        update=True,
        _sudo=True,
    )


def install_docker() -> None:
    apt.key(
        name="Add the Docker apt gpg key",
        src="https://download.docker.com/linux/ubuntu/gpg",
    )

    lsb_info = host.get_fact(LsbRelease)
    distro = lsb_info["id"].lower()
    code_name = lsb_info["codename"]

    # Not used?
    # arch = host.get_fact(Arch)
    # if arch == "x86_64":
    #     arch = "amd64"

    apt.repo(
        name="Add Docker repo",
        src=f"deb https://download.docker.com/linux/{distro} {code_name} stable",
    )

    packages = [
        "docker-ce",
        "docker-ce-cli",
        "containerd.io",
        # "docker-buildx-plugin",
        # "docker-compose-plugin",
    ]
    apt.packages(
        name="Install Docker packages",
        packages=packages,
        update=True,
        _sudo=True,
    )


def docker_group() -> None:
    user = host.get_fact(User)
    server.user(
        name=f"give docker group to {user!r}",
        user=user,
        groups=["docker"],
        _sudo=True,
    )


def start_docker_registry() -> None:
    server.shell(
        name="start docker registry",
        commands=[
            f"docker run -d -p {REGISTRY_PORT}:5000 --restart=always --name registry registry:latest || true"
        ],
    )

    systemd.service(
        name="restart docker daemon",
        service="docker",
        restarted=True,
        _sudo=True,
    )

    result = server.shell(
        name="check containers",
        commands=["docker container ls -a"],
    )
    print(result)


main()
