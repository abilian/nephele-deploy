"""
Minimal recipe to test smo-monorepo

assuming 0-setup-server.py has already been applied for base packages.

Warning: connection as user root.

pyinfra -y --user root ${SERVER_NAME} remote-install-test-smo.py
"""

from pyinfra import logger
from pyinfra.operations import files, python, server

SMO_MONO = "smo-monorepo"
SMO_MONO_URL = (
    "https://gitlab.eclipse.org/eclipse-research-labs/"
    "nephele-project/opencall-2/h3ni/smo-monorepo.git"
)
SMO_CLI = "/usr/local/bin/smo-cli"
GITS = "/root/gits"
REPO = f"{GITS}/{SMO_MONO}"
BRANCH = "main"


def log_callback(result):
    logger.info("-" * 60)
    if result.stdout:
        logger.info(result.stdout)
    if result.stderr:
        logger.info("stderr:")
        logger.info(result.stderr)
    logger.info("-" * 60)


def main() -> None:
    install_smo_mono_code()
    make_smo_test()
    show_smo_mono()


def install_smo_mono_code() -> None:
    files.directory(
        name=f"Create {GITS} directory",
        path=GITS,
    )

    server.shell(
        name=f"Clone/pull {SMO_MONO} source",
        commands=[
            f"[ -d {REPO} ] || git clone {SMO_MONO_URL} {REPO}",
            f"""
                cd {REPO}
                git fetch
                git checkout {BRANCH}
                git pull
            """,
        ],
    )


def make_smo_test() -> None:
    result = server.shell(
        name="Make test smo",
        commands=[
            f"""
            cd {REPO}
            uv venv -p3.12
            . .venv/bin/activate
            uv sync
            make test
            """
        ],
    )
    python.call(
        name="Show smo tests",
        function=log_callback,
        result=result,
    )


def show_smo_mono() -> None:
    result = server.shell(
        name="Exec smo-cli --help",
        commands=[f"cd {REPO} && .venv/bin/smo-cli --help"],
    )
    python.call(
        name="Show smo-cli --help",
        function=log_callback,
        result=result,
    )


main()
