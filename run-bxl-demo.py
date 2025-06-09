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
from constants import GITS, SMO_URL

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

# SMO= "smo-fork"
# SMO_URL = "https://gitlab.eclipse.org/sfermigier/smo-fork.git"
SMO = "smo"
LOCAL_IP = "127.0.0.1"


def main() -> None:
    check_server()
    setup_server()
    install_smo()
    make_brussels_images()
    check_images()


def setup_server() -> None:
    apt.packages(
        name="Install base packages",
        packages=BASE_APT_PACKAGES,
        update=True,
    )


def install_smo() -> None:
    files.directory(
        name=f"make {GITS} repository",
        path=GITS,
    )

    # # git.repo fails when the git repo does exists already, so:
    # server.shell(name=f"empty {GITS} repository", commands=[f"rm -fr {GITS}/{SMO}"])

    workdir = f"{GITS}/{SMO}"
    git.repo(
        name=f"clone/update {SMO} source",
        src=SMO_URL,
        dest=workdir,
        branch="main",
    )
    server.shell(
        name="build SMO",
        commands=[
            f"cd {workdir} && uv venv --python 3.12",
            f"cd {workdir} && uv sync",
        ],
    )


def make_brussels_images() -> None:
    workdir = f"{GITS}/{SMO}/examples/brussels-demo/"
    server.shell(
        name="make brussels images",
        commands=[
            f"cd {workdir} && perl -pi -e 's/10.0.3.53/{LOCAL_IP}/g' Makefile",
            f"cd {workdir} && make build-images && make push-images",
        ],
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
