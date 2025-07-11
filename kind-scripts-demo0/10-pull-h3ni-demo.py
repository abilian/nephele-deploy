"""
Minimal recipe to pull the git h3ni-demo

Warning:
    - assuming server already configured with git.
    - connection as user root.

pyinfra -y -vvv --user root ${SERVER_NAME} 10-pull-h3ni-demo.py
"""

from pyinfra.operations import files, git

from constants import GITS

DEMO_DIR = "h3ni-demos"
DEMO_URL = (
    "https://gitlab.eclipse.org/eclipse-research-labs/"
    "nephele-project/opencall-2/h3ni/h3ni-demos.git"
)


def main() -> None:
    pull_h3ni_demo()


def pull_h3ni_demo() -> None:
    files.directory(
        name=f"make {GITS} repository",
        path=GITS,
    )

    workdir = f"{GITS}/{DEMO_DIR}"
    git.repo(
        name=f"clone/update {DEMO_DIR} source",
        src=DEMO_URL,
        dest=workdir,
        branch="main",
    )


main()
