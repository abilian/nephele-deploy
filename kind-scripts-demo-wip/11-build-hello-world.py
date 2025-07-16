"""
Minimal recipe build for the hello-world app.

Warning: connection as user root.

assuming docker registry running.

pyinfra -y -vvv --user root ${SERVER_NAME} 11-build-hello-world.py
"""

# from pyinfra import host
# from pyinfra.facts.files import File
from pyinfra.operations import python, server

from common import log_callback
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
    build_image_hello_world()
    push_image_hello_world()
    check_images()


def build_image_hello_world() -> None:
    server.shell(
        name=f"Build {SRC_DOCKER_DIR}",
        commands=[f'cd {DEMO_DIR} && docker build -t "{IMG_TAG}" {SRC_DOCKER_DIR}'],
        _get_pty=True,
    )


def push_image_hello_world() -> None:
    server.shell(
        name=f"Push {IMG_TAG}",
        commands=[f'cd {DEMO_DIR} && docker push "{IMG_TAG}"'],
        _get_pty=True,
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
