"""
Minimal recipe to install smo-cli monorepo

Warning: connection as user root.

pyinfra -y -vvv --user root ${SERVER_NAME} 8-install-smo-cli-monorepo.py
"""

# from pyinfra import host
# from pyinfra.facts.files import File
from pyinfra.operations import apt, files, git, python, server

from common import check_server, log_callback
from constants import GITS

BASE_APT_PACKAGES = [
    "ca-certificates",
    "lsb-release",
    "git",
    "build-essential",
]

SMO_MONO = "smo-monorepo"
SMO_MONO_URL = (
    "https://gitlab.eclipse.org/eclipse-research-labs/"
    "nephele-project/opencall-2/h3ni/smo-monorepo.git"
)


def main() -> None:
    check_server()
    setup_server()
    install_smo_mono()
    show_smo_mono()


def setup_server() -> None:
    apt.packages(
        name="Install base packages",
        packages=BASE_APT_PACKAGES,
        update=True,
    )


def install_smo_mono() -> None:
    files.directory(
        name=f"make {GITS} repository",
        path=GITS,
    )

    workdir = f"{GITS}/{SMO_MONO}"
    git.repo(
        name=f"clone/update {SMO_MONO} source",
        src=SMO_MONO_URL,
        dest=workdir,
        branch="main",
    )
    server.shell(
        name="build smo from smo-monorepo",
        commands=[
            f"cd {workdir}/ && uv venv -p3.12",
            f"cd {workdir} && uv sync",
        ],
    )
    target = f"{GITS}/{SMO_MONO}/.venv/bin/smo-cli"
    server.shell(
        name="Copy smo-cli to /usr/local/bin",
        commands=[f"cp -f {target} /usr/local/bin/"],
    )


def show_smo_mono() -> None:
    result = server.shell(
        name="Show '/usr/local/bin/smo-cli --help'",
        commands=["/usr/local/bin/smo-cli --help"],
    )
    python.call(
        name="Show '/usr/local/bin/smo-cli --help'",
        function=log_callback,
        result=result,
    )


main()
