"""
Minimal recipe to install docker registry.

pyinfra -y -vv --user root HOST 5-install-docker-registry.py
"""

from pyinfra.operations import python, server, systemd

from common import check_server, log_callback

REGISTRY_PORT = 5000


def main() -> None:
    start_docker_registry()


def start_docker_registry() -> None:
    server.shell(
        name="Start docker registry",
        commands=[
            f"docker run -d -p {REGISTRY_PORT}:5000 --restart=always --name registry registry:latest || true"
        ],
    )

    systemd.service(
        name="Restart docker daemon",
        service="docker",
        restarted=True,
    )

    result = server.shell(
        name="Check containers",
        commands=["docker container ls -a"],
    )
    python.call(
        name="Check containers",
        function=log_callback,
        result=result,
    )


main()
