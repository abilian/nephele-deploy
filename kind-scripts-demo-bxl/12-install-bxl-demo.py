"""
Minimal recipe to install smo nephele

assuming 0-setup-server.py has already been applied for base packages.

Warning: connection as user root.

# (smo) root@ubuntu-16gb-hel1-4:~/gits/smo# kubectl get services --all-namespaces

pyinfra -y -v --user root ${SERVER_NAME} 12-install-bxl-demo.py
"""

from pyinfra.operations import files, python, server

from common import log_callback
from constants import GITS

SMO_NEPHE = "smo"
SMO_NEPHE_URL = (
    "https://gitlab.eclipse.org/eclipse-research-labs/nephele-project/smo.git"
)
SMO_CLI = "/usr/local/bin/smo-cli"
BRANCH = "main"
LOCAL_IP = "127.0.0.1"
INTERNAL_IP = "host.docker.internal"
REPO = f"{GITS}/{SMO_NEPHE}"
DEMO = f"{REPO}/examples/brussels-demo/"


def main() -> None:
    configure_demo_addresses()
    make_brussels_demo_images()
    show_docker_images()
    check_images()
    make_package_artifacts()
    make_push_artifacts()
    make_test_manifest_an_artifacts()
    create_existing_artifacts()


def configure_demo_addresses() -> None:
    server.shell(
        name="Replace IP in smo demo files",
        commands=[
            f"""\
                cd {REPO}
                . .venv/bin/activate

                cd {DEMO}
                perl -pi -e 's/10.0.3.53/{LOCAL_IP}/g' Makefile
                perl -pi -e 's/10.0.3.53/{LOCAL_IP}/g' create-existing-artifact.sh
                cd {DEMO}/hdag
                perl -pi -e 's/10.0.3.53/{INTERNAL_IP}/g' hdag.yaml
                cd {DEMO}/image-compression-vo/templates
                perl -pi -e 's/10.0.3.53/{INTERNAL_IP}/g' deployment.yaml
                cd {DEMO}/image-detection/templates
                perl -pi -e 's/10.0.3.53/{INTERNAL_IP}/g' deployment.yaml
                cd {DEMO}/noise-reduction/templates
                perl -pi -e 's/10.0.3.53/{INTERNAL_IP}/g' deployment.yaml

                cd {DEMO}
                perl -pi -e 's;REGISTRY_URL=.*;REGISTRY_URL="http://{INTERNAL_IP}:5000";g' create-existing-artifact.sh

            """
        ],
        _shell_executable="/bin/bash",
        _get_pty=True,
    )


def make_brussels_demo_images() -> None:
    server.shell(
        name="Make brussels images",
        commands=[
            f"""\
                cd {REPO}
                . .venv/bin/activate
                cd {DEMO}
                make build-images && make push-images
            """
        ],
        _shell_executable="/bin/bash",
        _get_pty=True,
    )


def show_docker_images() -> None:
    result = server.shell(
        name="Show brussels images",
        commands=["docker images"],
    )
    python.call(
        name="Show brussels images",
        function=log_callback,
        result=result,
    )


def check_images() -> None:
    result = server.shell(
        name="Check images in local docker registry",
        commands=[
            "curl -s -X GET http://localhost:5000/v2/_catalog",
        ],
    )
    python.call(
        name="Show Check images in local docker registry",
        function=log_callback,
        result=result,
    )


def make_package_artifacts() -> None:
    result = server.shell(
        name="Make package artifacts",
        commands=[
            f"""\
                cd {REPO}
                . .venv/bin/activate
                cd {DEMO}
                make package-artifacts
            """,
        ],
        _shell_executable="/bin/bash",
        _get_pty=True,
    )
    python.call(
        name="Show package artifacts",
        function=log_callback,
        result=result,
    )


def make_push_artifacts() -> None:
    result = server.shell(
        name="Make push artifacts",
        commands=[
            f"""\
                cd {REPO}
                . .venv/bin/activate
                cd {DEMO}
                make push-artifacts
            """,
        ],
        _shell_executable="/bin/bash",
        _get_pty=True,
    )
    python.call(
        name="Show push artifacts",
        function=log_callback,
        result=result,
    )


def make_test_manifest_an_artifacts() -> None:
    result = server.shell(
        name="Make test manifest artifacts",
        commands=[
            f"""\
                cd {REPO}
                . .venv/bin/activate
                cd {DEMO}
                hdarctl manifest  http://127.0.0.1:5000/test/image-compression-vo:0.1.0
            """,
        ],
        _shell_executable="/bin/bash",
        _get_pty=True,
    )
    python.call(
        name="Show manifest artifacts",
        function=log_callback,
        result=result,
    )


def create_existing_artifacts() -> None:
    result = server.shell(
        name="Run create-existing-artifact.sh",
        commands=[
            f"""\
                cd {REPO}
                . .venv/bin/activate

                cd {DEMO}

                docker compose ps smo

                bash create-existing-artifact.sh
            """,
        ],
        _shell_executable="/bin/bash",
        _get_pty=True,
    )
    python.call(
        name="Show create-existing-artifact.sh output",
        function=log_callback,
        result=result,
    )


main()
