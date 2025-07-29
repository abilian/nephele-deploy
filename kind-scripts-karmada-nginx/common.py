from pyinfra import host, logger
from pyinfra.facts.server import LsbRelease


def check_server() -> None:
    logger.info("Starting Common Prerequisite Checks")
    lsb_info = host.get_fact(LsbRelease)
    is_apt_based = lsb_info["id"].lower() in ["ubuntu", "debian"]
    assert is_apt_based, (
        f"Unsupported OS: {lsb_info['id']}. This script is designed for Debian/Ubuntu."
    )


def log_callback(result):
    logger.info("-" * 60)
    if result.stdout:
        logger.info(result.stdout)
    if result.stderr:
        logger.info("stderr:")
        logger.info(result.stderr)
    logger.info("-" * 60)
