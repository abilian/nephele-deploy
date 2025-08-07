"""
Minimal recipe to pull the git h3ni-demo

Warning:
    - assuming server already configured with git.
    - connection as user root.

pyinfra -y -vvv --user root ${SERVER_NAME} 11-pull-h3ni-demo.py
"""

from pyinfra.operations import files, server

from constants import GITS


SMO_MONOREPO_URL = (
    "https://gitlab.eclipse.org/eclipse-research-labs/"
    "nephele-project/opencall-2/h3ni/smo-monorepo.git"
)
SMO_DIR = "smo-monorepo"
DEMO_DIR = "h3ni-demos"
DEMO_URL = (
    "https://gitlab.eclipse.org/eclipse-research-labs/"
    "nephele-project/opencall-2/h3ni/h3ni-demos.git"
)
REPO = f"{GITS}/{DEMO_DIR}"
SMO_REPO = f"{GITS}/{SMO_DIR}"


def main() -> None:
    make_git_directory()
    pull_smo_monorepo()
    pull_h3ni_demo()


def make_git_directory() -> None:
    files.directory(
        name=f"Create {GITS} directory",
        path=GITS,
    )


def pull_smo_monorepo() -> None:
    server.shell(
        name=f"Clone/pull smo-monorepo source",
        commands=[
            f"[ -d {SMO_REPO} ] || git clone {SMO_MONOREPO_URL} {SMO_REPO}",
            f"""
            cd {SMO_REPO}
            git clean -fxd
            git pull
            """,
        ],
    )


def pull_h3ni_demo() -> None:
    server.shell(
        name=f"Clone/pull {DEMO_DIR} source",
        commands=[
            f"[ -d {REPO} ] || git clone {DEMO_URL} {REPO}",
            f"""
            cd {REPO}
            git clean -fxd
            git pull
            """,
        ],
    )

    server.shell(
        name=f"uv sync {DEMO_DIR}",
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
