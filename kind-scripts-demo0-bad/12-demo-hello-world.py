"""
Minimal recipe build for the hello-world app.

Warning: connection as user root.

pyinfra -y -vvv --user root ${SERVER_NAME} 12-demo-hello-world.py
"""

from pyinfra.operations import server, python
from common import log_callback

from constants import GITS

TOP_DIR = f"{GITS}/h3ni-demos/"
SMO_CLI = "/usr/local/bin/smo-cli"


def main() -> None:
    install_hello_world()


def install_hello_world():
    server.shell(
        name="Remove prior hello-world-graph",
        commands=[(f"yes | {SMO_CLI} graph remove hello-world-graph || true")],
        _get_pty=True,
    )
    server.shell(
        name="Deploy using smo-cli",
        commands=[
            (
                f"cd {TOP_DIR} && . .venv/bin/activate && "
                "cd 0-hello-world-demo && inv all"
            )
        ],
        _get_pty=True,
    )
    result = server.shell(
        name="Show graph list",
        commands=[f"{SMO_CLI} graph list"],
        _get_pty=True,
    )
    python.call(
        name="Show graph list",
        function=log_callback,
        result=result,
    )


main()
