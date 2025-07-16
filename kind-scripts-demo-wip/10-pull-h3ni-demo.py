"""
Minimal recipe to pull the git h3ni-demo

Warning:
    - assuming server already configured with git.
    - connection as user root.

pyinfra -y -vvv --user root ${SERVER_NAME} 10-pull-h3ni-demo.py
"""

from pyinfra.operations import files, git, server

from constants import GITS

DEMO_DIR = "h3ni-demos"
DEMO_URL = (
    "https://gitlab.eclipse.org/eclipse-research-labs/"
    "nephele-project/opencall-2/h3ni/h3ni-demos.git"
)
REPO = f"{GITS}/{DEMO_DIR}"


def main() -> None:
    pull_h3ni_demo()


def pull_h3ni_demo() -> None:
    def install_smo_mono() -> None:
        files.directory(
            name=f"Create {GITS} directory",
            path=GITS,
        )

        server.shell(
            name=f"Clone/pull {DEMO_DIR} source",
            commands=[
                f"[ [ -d {REPO} ] || git clone {DEMO_URL} {REPO}",
                f"cd  {REPO}; git pull",
            ],
        )

        server.shell(
            name="Prepare {DEMO_DIR}",
            commands=[f"cd {REPO}; uv venv -p3.12; . .ven/bin/activate; uv sync"],
        )


main()
