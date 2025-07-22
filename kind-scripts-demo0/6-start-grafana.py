"""
Minimal recipe to start grafana.

assuming 0-setup-server.py has already been applied for base packages.

NOTA: will be part of Promethus stack later

pyinfra -y -vv --user root ${SERVER_NAME} 6-start-grafana.py
"""

from pyinfra.operations import server

from common import check_server


def main() -> None:
    start_grafana()
    check_grafana_admin()


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
                "docker run -d -p 0.0.0.0:3000:3000 "
                "--restart=always "
                "--name=grafana "
                "-e GF_SECURITY_ADMIN_USER=admin "
                "-e GF_SECURITY_ADMIN_PASSWORD=prom-operator "
                "grafana/grafana-enterprise"
            )
        ],
        # _ignore_errors=True,
    )
    server.wait(
        name="Wait Grafana ready",
        port=3000,
    )


def check_grafana_admin() -> None:
    server.shell(
        name="Check grafana ",
        commands=[
            "sleep 10",
            "curl  -v -s -u admin:admin http://127.0.0.1:3000/api/user 2>&1 | tee /root/test_grafana.txt",
            "curl  -v -s -u admin:admin http://localhost:3000/api/dashboards/db 2>&1 | tee -a  /root/test_grafana.txt",
            # "curl -s -u admin:admin http://127.0.0.1:3000",
            #'| grep -q "isGrafanaAdmin" '
        ],
        _get_pty=True,
        # _ignore_errors=True,
        _shell_executable="/bin/bash",
    )


main()
