"""
Minimal recipe to start grafana.

pyinfra -y -vv --user root ${SERVER_NAME} 4-2-start-grafana.py
"""

from pyinfra.operations import server

from common import check_server


def main() -> None:
    check_server()
    start_grafana()


def start_grafana() -> None:
    server.shell(
        name="Kill grafana",
        commands="docker kill grafana",
        _ignore_errors=True,
    )
    server.shell(
        name="Remove grafana",
        commands="docker rm grafana",
        _ignore_errors=True,
    )
    server.shell(
        name="Start grafana",
        commands=[
            (
                "docker run -d -p 3000:3000 --restart=always "
                "--name=grafana "
                "-e GF_SECURITY_ADMIN_USER=admin "
                "-e GF_SECURITY_ADMIN_PASSWORD=admin "
                "grafana/grafana-enterprise"
            )
        ],
        # _ignore_errors=True,
    )


main()
