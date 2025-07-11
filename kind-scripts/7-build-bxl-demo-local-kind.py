"""
Minimal recipe to deploy BXL demo on local docker registry
- brussels sample

Warning: connection as user root.

pyinfra -y -vvv --user root HOST 7-build-bxl-demo-local-kind.py
"""

# from pyinfra import host
# from pyinfra.facts.files import File
from pyinfra.operations import apt, files, git, python, server

from common import check_server, log_callback
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
    make_brussels_demo_images()
    show_docker_images()
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


def make_brussels_demo_images() -> None:
    workdir = f"{GITS}/{SMO}/examples/brussels-demo/"
    server.shell(
        name="Make brussels images",
        commands=[
            f"cd {workdir} && perl -pi -e 's/10.0.3.53/{LOCAL_IP}/g' Makefile",
            # f"cd {workdir} && make build-images && make push-images",
            f"cd {workdir} && make build-images && make push-images",
        ],
    )


def show_docker_images() -> None:
    result = server.shell(
        name="Show brussels images",
        commands=["docker images"],
    )
    python.call(
        name="Show brussels images",
        function=log_callback,
        result=result,
    )


def check_images() -> None:
    result = server.shell(
        name="Check images in local docker registry",
        commands=[
            "curl -X GET http://localhost:5000/v2/_catalog",
        ],
    )
    python.call(
        name="Show Check images in local docker registry",
        function=log_callback,
        result=result,
    )


main()
