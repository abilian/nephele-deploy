"""
Minimal recipe to deploy
- brussels sample

Warning: connection as user root.

pyinfra -y -vvv --user root HOST deploy-root-brussels.py
"""

from pyinfra import host, logger
from pyinfra.facts.server import LsbRelease
from pyinfra.operations import apt, git, server

REGISTRY_PORT = 5000
# SMO= "smo-fork"
# SMO_URL = "https://gitlab.eclipse.org/sfermigier/smo-fork.git"
GITS = "/root/gits"
SMO = "smo"
SMO_URL = "https://gitlab.eclipse.org/eclipse-research-labs/nephele-project/smo.git"
LOCAL_IP = "127.0.0.1"


def main() -> None:
    check_server()
    setup_server()
    install_uv()
    install_smo_source()
    fetch_hdarctl_binary()
    make_brussels_images()
    check_images()


def check_server() -> None:
    logger.info("Starting Common Prerequisite Checks")
    lsb_info = host.get_fact(LsbRelease)
    is_apt_based = lsb_info["id"].lower() in ["ubuntu", "debian"]
    assert is_apt_based, (
        f"Unsupported OS: {lsb_info['id']}. This script is designed for Debian/Ubuntu."
    )


def setup_server() -> None:
    packages = [
        "ca-certificates",
        "lsb-release",
        "curl",
        "wget",
        "tar",
        "gnupg",
        "git",
        "vim",
        "build-essential",
    ]
    apt.packages(
        packages=packages,
        update=True,
    )


def install_uv() -> None:
    server.shell(
        name="install uv",
        commands=[
            "[ -f ${HOME}/.local/bin/uv ] || curl -LsSf https://astral.sh/uv/install.sh | sh"
        ],
        _get_pty=True,
    )
    server.shell(
        name="configure .bashrc",
        commands=[
            "mkdir -p ~/bin",
            "echo 'export PATH=\"~/.local/bin:~/bin:$PATH\"' >> ~/.bashrc",
            "echo 'export UV_LINK_MODE=hardlink' >> ~/.bashrc",
        ],
        _get_pty=True,
    )


def install_smo_source() -> None:
    server.shell(name=f"make {GITS} repository", commands=[f"mkdir -p {GITS}"])

    # # git.repo fails when the git repo does exists already, so:
    # server.shell(name=f"empty {GITS} repository", commands=[f"rm -fr {GITS}/{SMO}"])

    git.repo(
        src=SMO_URL,
        dest=f"{GITS}/{SMO}",
        branch="main",
        pull=True,
        rebase=False,
        user="root",
        group="root",
        ssh_keyscan=False,
        update_submodules=False,
        recursive_submodules=False,
    )
    server.shell(
        name="build SMO",
        commands=[
            f"cd {GITS}/{SMO} && /root/.local/bin/uv venv --python 3.12",
            f". {GITS}/{SMO}/.venv/bin/activate",
            f"cd {GITS}/{SMO} && /root/.local/bin/uv sync",
        ],
        _get_pty=True,
    )


def fetch_hdarctl_binary() -> None:
    server.shell(
        name="fetch hdarctl binary",
        commands=[
            """[ -d /root/bin/hdarctl ] || {
                cd /root/bin
                curl -O https://gitlab.eclipse.org/eclipse-research-labs/nephele-project/nephele-development-sandbox/-/raw/main/tools/hdarctl
                chmod +x hdarctl
                /root/bin/hdarctl -h
            }""",
        ],
        _get_pty=True,
    )


def make_brussels_images() -> None:
    server.shell(
        name="make brussels images",
        commands=[
            f"cd {GITS}/{SMO}/examples/brussels-demo/ && perl -pi -e 's/10.0.3.53/{LOCAL_IP}/g' Makefile",
            f"cd {GITS}/{SMO}/examples/brussels-demo/ && make build-images && make push-images",
        ],
        _get_pty=True,
    )


def check_images() -> None:
    server.shell(
        name="check images in registry",
        commands=["curl -X GET http://localhost:5000/v2/_catalog"],
    )


main()
