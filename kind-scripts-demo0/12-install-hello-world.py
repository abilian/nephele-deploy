"""
Minimal recipe build for the hello-world app.

Warning: connection as user root.

assuming docker registry running.

pyinfra -y -vvv --user root ${SERVER_NAME} 12-install-hello-world.py
"""


from pyinfra.operations import server

from constants import GITS

HOST_ADDR = "127.0.0.1"
REGISTRY = f"{HOST_ADDR}:5000"
SRC_DOCKER_DIR = "src/hello-world"
IMG_TAG = f"{REGISTRY}/hello-world"
HDAR = f"http://{HOST_ADDR}:5000"
PROJECT = "demo0"
DEMO_DIR = f"{GITS}/h3ni-demos/0-hello-world-demo/"
TOP_DIR = f"{GITS}/h3ni-demos/"


def main() -> None:
    install_hello_world()


def install_hello_world():
    server.shell(
        name="Make venv python 3.12",
        commands=[f"cd {TOP_DIR} && uv venv -p3.12"],
        _get_pty=True,
    )
    server.shell(
        name="uv sync",
        commands=[f"cd {TOP_DIR} && . .venv/bin/activate && uv sync"],
        _get_pty=True,
    )
    server.shell(
        name="Install python packages",
        commands=[
            f"cd {TOP_DIR} && . .venv/bin/activate && uv pip install pyyaml invoke"
        ],
        _get_pty=True,
    )
    server.shell(
        name="Make package artifacts",
        commands=[
            (
                f"cd {TOP_DIR} && . .venv/bin/activate && "
                "cd 0-hello-world-demo && inv package-artifacts"
            )
        ],
        _get_pty=True,
    )
    server.shell(
        name="Push package artifacts",
        commands=[
            (
                f"cd {TOP_DIR} && . .venv/bin/activate && "
                "cd 0-hello-world-demo && inv push-artifacts"
            )
        ],
        _get_pty=True,
    )
    server.shell(
        name="Initialize smo-cli",
        commands=[(f"cd {TOP_DIR} && . .venv/bin/activate && smo-cli init")],
        _get_pty=True,
    )
    server.shell(
        name="Deploy using smo-cli",
        commands=[
            (
                f"cd {TOP_DIR} && . .venv/bin/activate && "
                "cd 0-hello-world-demo && inv deploy-using-cli"
            )
        ],
        _get_pty=True,
    )


main()
