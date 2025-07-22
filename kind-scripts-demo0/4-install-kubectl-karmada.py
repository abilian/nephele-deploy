"""
Minimal recipe to deploy kind kubernetes engine and tools on a ubuntu like distribution.

assuming 0-setup-server.py has already been applied for base packages.

pyinfra -y -vv --user root ${SERVER_NAME} 4-install-kubectl-karmada.py
"""

from pyinfra import host
from pyinfra.facts.files import File
from pyinfra.operations import apt, files, python, server, snap, systemd

from common import log_callback
from constants import GITS


HOST_CONFIG_FILENAME = "host.config"
KUBE_CONF_DIR = "/root/.kube"
KUBE_CONF_PATH = f"{KUBE_CONF_DIR}/config"
HOST_CONF_PATH = f"{KUBE_CONF_DIR}/{HOST_CONFIG_FILENAME}"
KUBECONFIG = HOST_CONF_PATH


def main() -> None:
    install_karmada()


def install_karmada() -> None:
    INSTALLER_URL = (
        "https://raw.githubusercontent.com/karmada-io/"
        "karmada/master/hack/install-cli.sh"
    )
    # VERSION='v1.14.1'
    files.file(
        name="Remove old karmada CLI",
        path="/usr/local/bin/kubectl-karmada",
        present=False,
    )
    server.shell(
        name="Install Karmada CLI",
        commands=[
            f"curl -s {INSTALLER_URL} | sudo bash -s kubectl-karmada",
        ],
        _get_pty=True,
    )

    result = server.shell(
        name="Get kubectl-karmada version",
        commands=[
            "kubectl-karmada version",
        ],
    )
    python.call(
        name="Show kubectl-karmada version",
        function=log_callback,
        result=result,
    )


# def install_karmada2():
#     REPO = f"{GITS}/karmada"
#     KARMADA_URL = "https://github.com/karmada-io/karmada.git"
#     files.file(
#         name="Remove old karmada CLI",
#         path="/usr/local/bin/kubectl-karmada",
#         present=False,
#     )
#     server.shell(
#         name=f"Clone/pull {REPO}",
#         commands=[
#             f"[ -d {REPO} ] || git clone --depth 1 {KARMADA_URL} {REPO}",
#             f"cd {REPO}; git pull",
#         ],
#     )
#     server.shell(
#         name=f"Clone/pull {REPO}",
#         commands=[
#             f"[ -d {REPO} ] || git clone --depth 1 {KARMADA_URL} {REPO}",
#             f"cd {REPO}; git pull",
#         ],
#     )
#     server.shell(
#         name="Install Karmada",
#         commands=[
#             f"""export KUBECONFIG={KUBECONFIG}
#                 cd {REPO}
#                 hack/local-up-karmada.sh
#                 cp -f karmada.config {KUBE_CONF_DIR}
#                 cp -f members.config {KUBE_CONF_DIR}
#             """
#         ],
#     )


main()
