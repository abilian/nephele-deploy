"""
Minimal recipe to install smo-cli nephele

assuming 0-setup-server.py has already been applied for base packages.

Warning: connection as user root.

pyinfra -y -vvv --user root ${SERVER_NAME} 1-install-nephele-smo.py
"""

# from pyinfra import host
# from pyinfra.facts.files import File
from pyinfra.operations import files, python, server
from common import log_callback
from constants import GITS

SMO_NEPHE = "smo"
SMO_NEPHE_URL = (
    "https://gitlab.eclipse.org/eclipse-research-labs/nephele-project/smo.git"
)
SMO_CLI = "/usr/local/bin/smo-cli"
BRANCH = "main"


def main() -> None:
    remove_prior_smo_cli()
    install_smo()


def remove_prior_smo_cli() -> None:
    files.file(
        name=f"Remove {SMO_CLI} if exists",
        path=SMO_CLI,
        present=False,
        force=True,
    )


def install_smo() -> None:
    files.directory(
        name=f"Create {GITS} directory",
        path=GITS,
    )

    REPO = f"{GITS}/{SMO_NEPHE}"
    server.shell(
        name=f"Clone/pull {SMO_NEPHE} source",
        commands=[
            f"[ -d {REPO} ] || git clone {SMO_NEPHE_URL} {REPO}",
            f"""
                cd {REPO}
                git fetch
                git checkout {BRANCH}
                git pull
            """,
        ],
    )

    server.shell(
        name="Build smo",
        commands=[
            f"""
                cd {REPO}
                uv venv -p3.12
                . .venv/bin/activate
                uv sync
            """
        ],
    )


main()
