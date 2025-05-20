"""
Minimal recipe to deploy
- full docker dependencies and registry

pyinfra -y -vvv --user USER HOST deploy-docker.py
"""

from pyinfra import host, logger
from pyinfra.facts.server import Arch, LsbRelease, User
from pyinfra.operations import apt, server

REGISTRY_PORT = 5000


def main() -> None:
    check_server()
    setup_server()
    install_docker_key()
    install_docker_source_list()
    install_docker_packages()
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
        packages=packages,
        update=True,
        _sudo=True,
    )


def install_docker_key() -> None:
    lsb_info = host.get_fact(LsbRelease)
    distro = lsb_info["id"].lower()
    server.shell(
        name="mkdir keyrings",
        commands=[
            "mkdir -p /etc/apt/keyrings",
        ],
        _sudo=True,
    )
    server.shell(
        name="fetch docker gpg key",
        commands=[
            # "rm -f /etc/apt/keyrings/docker.asc",
            # f"curl -fsSL https://download.docker.com/linux/{distro}/gpg | gpg --yes --dearmor -o /etc/apt/keyrings/docker.asc",
            f"curl -fsSL https://download.docker.com/linux/{distro}/gpg |  apt-key add -"
            # "chmod a+r /etc/apt/keyrings/docker.asc",
        ],
        _sudo=True,
        _get_pty=True,
    )


def install_docker_source_list() -> None:
    lsb_info = host.get_fact(LsbRelease)
    distro = lsb_info["id"].lower()
    code_name = lsb_info["codename"]
    arch = host.get_fact(Arch)
    if arch == "x86_64":
        # arch = "i386"
        arch = "amd64"
    cmd = f"deb [arch={arch} signed-by=/etc/apt/keyrings/docker.asc] https://download.docker.com/linux/{distro} {code_name} stable"
    server.shell(
        name="fetch docker repository",
        commands=[
            f'echo "{cmd}" | sudo tee /etc/apt/sources.list.d/docker.list > /dev/null',
        ],
        _sudo=True,
        _get_pty=True,
    )


def install_docker_packages() -> None:
    packages = [
        "docker-ce",
        "docker-ce-cli",
        "containerd.io",
        # "docker-buildx-plugin",
        # "docker-compose-plugin",
    ]
    # server.shell(
    #     name="clean docker installed",
    #     commands=["dpkg --purge --force-all containerd docker.io runc"],
    #     _sudo=True,
    # )
    apt.packages(
        packages=packages,
        update=True,
        _sudo=True,
    )


def docker_group() -> None:
    user = host.get_fact(User)
    server.shell(
        name=f"give docker group to {user!r}",
        commands=[
            f"usermod -aG docker {user}",
        ],
        _sudo=True,
    )


def start_docker_registry() -> None:
    server.shell(
        name="start docker registry",
        commands=[
            f"docker run -d -p {REGISTRY_PORT}:5000 --restart=always --name registry registry:latest || true"
        ],
    )
    server.shell(
        name="restart docker daemon",
        commands=["systemctl restart docker"],
        _sudo=True,
    )
    result = server.shell(
        name="check containers",
        commands=["docker container ls -a"],
    )
    print(result)


main()
