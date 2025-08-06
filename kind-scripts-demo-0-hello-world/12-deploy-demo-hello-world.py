"""
Minimal recipe build for the hello-world app.

Warning: connection as user root.

pyinfra -y -vvv --user root ${SERVER_NAME} 12-deploy-demo-hello-world.py
"""

from pyinfra.operations import server, python
from common import log_callback

from constants import GITS

TOP_DIR = f"{GITS}/h3ni-demos/"
SMO_URL = "http://localhost:8000"


def graph_delete_cmd(graph: str) -> str:
    return f'curl -X "DELETE" {SMO_URL}/graphs/{graph}'


def main() -> None:
    install_hello_world()


def install_hello_world():
    for name in ("hello-world-graph", "image-detection-graph"):
        cmd = graph_delete_cmd(name)
        server.shell(
            name="Remove prior known graphes",
            # commands=[(f"yes | {SMO_CLI} graph remove {name} || true")],
            commands=[f"{cmd} || true"],
            _get_pty=True,
        )
    server.shell(
        name="Deploy hello-world-graph",
        commands=[
            (
                f"""
                cd {TOP_DIR}
                . .venv/bin/activate
                
                cd 0-hello-world-demo
                inv all
                """
            )
        ],
        _get_pty=True,
    )

    result = server.shell(
        name="Find all kubernetes pods",
        commands=["kubectl get pods -A"],
        _get_pty=True,
    )
    python.call(
        name="Show all kubernetes pods",
        function=log_callback,
        result=result,
    )

    result = server.shell(
        name="Get graph list",
        commands=[f"{SMO_CLI} graph list"],
        _get_pty=True,
    )
    python.call(
        name="Show graph list",
        function=log_callback,
        result=result,
    )


main()
