"""
Minimal recipe to install smo-cli monorepo

Warning: connection as user root.

pyinfra -y -vvv --user root ${SERVER_NAME} 0-2-install-smo-cli-monorepo.py
"""

import io

# from pyinfra import host
# from pyinfra.facts.files import File
from pyinfra.operations import files, python, server

from common import log_callback

SMO_CLI = "/usr/local/bin/smo-cli"

SMO_CONF = """\
grafana:
  host: http://localhost:3000
  username: admin
  password: admin
prometheus_host: http://localhost:9090
helm:
  insecure_registry: true
scaling:
  interval_seconds: 30
"""


def main() -> None:
    init_smo_mono()


def init_smo_mono() -> None:
    files.put(
        name="Force smo config",
        src=io.StringIO(SMO_CONF),
        dest="/root/.smo/config",
    )
    result = server.shell(
        name="Initialize smo-cli",
        commands=[f"{SMO_CLI} init"],
    )
    python.call(
        name="Initialize smo-cli",
        function=log_callback,
        result=result,
    )


def show_smo_mono() -> None:
    result = server.shell(
        name=f"Show {SMO_CLI} graph list",
        commands=[f"{SMO_CLI} graph list"],
    )
    python.call(
        name=f"Show {SMO_CLI} graph list",
        function=log_callback,
        result=result,
    )


main()
