"""
Minimal recipe to install smo-cli monorepo

Warning: connection as user root.

pyinfra -y -vvv --user root ${SERVER_NAME} 0-2-install-smo-cli-monorepo.py
"""

# from pyinfra import host
# from pyinfra.facts.files import File
from pyinfra.operations import apt, files, python, server
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
SMO_CLI = "/usr/local/bin/smo-cli"


def main() -> None:
    check_server()
    setup_server()
    remove_prior_smo_cli()
    install_smo_mono()
    show_smo_mono()


def setup_server() -> None:
    apt.packages(
        name="Install base packages",
        packages=BASE_APT_PACKAGES,
        update=True,
    )


def remove_prior_smo_cli() -> None:
    files.file(
        name=f"Remove {SMO_CLI} if exists",
        path=SMO_CLI,
        present=False,
        force=True,
    )


def install_smo_mono() -> None:
    files.directory(
        name=f"Create {GITS} directory",
        path=GITS,
    )

    REPO = f"{GITS}/{SMO_MONO}"
    server.shell(
        name=f"Clone/pull {SMO_MONO} source",
        commands=[
            f"[ -x {SMO_CLI} ] || [ -d {REPO} ] || git clone {SMO_MONO_URL} {REPO}",
            f"""[ -x {SMO_CLI} ] || {{
                    cd {REPO}
                    git fetch
                    git checkout scaling
                    git pull
                }}
            """,
        ],
    )

    server.shell(
        name="Build smo from smo-monorepo",
        commands=[
            f"""[ -x {SMO_CLI} ] || {{
                    cd {REPO}
                    uv venv -p3.12
                    . .venv/bin/activate
                    uv sync
                    cp .venv/bin/smo-cli /usr/local/bin
                }}
            """
        ],
    )


def show_smo_mono() -> None:
    result = server.shell(
        name=f"Show {SMO_CLI} --help",
        commands=[f"{SMO_CLI} --help"],
    )
    python.call(
        name=f"Show {SMO_CLI} --help",
        function=log_callback,
        result=result,
    )


main()
