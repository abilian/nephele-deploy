from pyinfra import host, logger
from pyinfra.facts.server import LsbRelease, User
from pyinfra.operations import apt, server, systemd


def check_server() -> None:
    logger.info("Starting Common Prerequisite Checks")
    lsb_info = host.get_fact(LsbRelease)
    is_apt_based = lsb_info["id"].lower() in ["ubuntu", "debian"]
    assert is_apt_based, (
        f"Unsupported OS: {lsb_info['id']}. This script is designed for Debian/Ubuntu."
    )
