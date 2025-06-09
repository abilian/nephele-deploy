"""
Minimal recipe to deploy
- brussels sample

Warning: connection as user root.

pyinfra -y -vvv --user root HOST deploy-root-brussels.py
"""

from pyinfra import host
from pyinfra.facts.files import File
from pyinfra.operations import apt, git, server, files, python

from common import check_server

BASE_APT_PACKAGES = [
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
    install_smo()
    fetch_hdarctl_binary()
    make_brussels_images()
    check_images()


def setup_server() -> None:
    apt.packages(
        name="Install base packages",
        packages=BASE_APT_PACKAGES,
        update=True,
    )


def install_uv() -> None:
    fact = host.get_fact(File, "/usr/bin/uv")
    if not fact:
        server.shell(
            name="install uv",
            commands=[
                "curl -LsSf https://astral.sh/uv/install.sh | sh"
            ],
        )
        server.shell(
            name="copy uv to /usr/bin",
            commands=[
                "cp /root/.local/bin/uv /usr/bin/uv",
            ]
        )


def install_smo() -> None:
    files.directory(
        name=f"make {GITS} repository",
        path=GITS,
    )

    # # git.repo fails when the git repo does exists already, so:
    # server.shell(name=f"empty {GITS} repository", commands=[f"rm -fr {GITS}/{SMO}"])

    git.repo(
        name=f"clone/update {SMO} source",
        src=SMO_URL,
        dest=f"{GITS}/{SMO}",
        branch="main",
    )
    server.shell(
        name="build SMO",
        commands=[
            f"cd {GITS}/{SMO} && uv venv --python 3.12",
            f"cd {GITS}/{SMO} && uv sync",
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
    files.put(
        name="put check-registry.py script",
        src="server-scripts/check-registry.py",
        dest="/root/check-registry.py",
    )
    server.shell(
        name="run check-registry.py script",
        commands=["python3 /root/check-registry.py"],
    )


main()
