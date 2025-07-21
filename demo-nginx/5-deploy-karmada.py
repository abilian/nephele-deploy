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


# HOST_CONFIG_FILENAME = "host.config"
# KUBE_CONF_DIR = "/root/.kube"
# KUBE_CONF_PATH = f"{KUBE_CONF_DIR}/config"
# HOST_CONF_PATH = f"{KUBE_CONF_DIR}/{HOST_CONFIG_FILENAME}"
# KUBECONFIG = HOST_CONF_PATH

# HOST_CONFIG_FILENAME = "host.config"
# KUBE_CONF_DIR = "/root/.kube"
# KUBE_CONF_PATH = f"{KUBE_CONF_DIR}/config"
# HOST_CONF_PATH = f"{KUBE_CONF_DIR}/{HOST_CONFIG_FILENAME}"
KUBECONFIG = "/root/.kube/config"


def main() -> None:
    deploy_karmada()


def deploy_karmada() -> None:
    VERSION = "v1.14.1"
    CRDS = (
        f"https://github.com/karmada-io/karmada/releases/download/{VERSION}/crds.tar.gz"
    )
    LOG = "/root/log_karmada_init.txt"
    RETRY = 12  # 4 min
    WAIT = 30
    # server.shell(
    #     name="Remove old karmada configuration if needed",
    #     commands="kubectl karmada deinit --purge-namespace || true",
    #     # "rm -fr /var/lib/karmada-etcd ",
    # )

    server.shell(
        name="Deploy karmada configuration",
        commands=[
            f"""
            echo "" > {LOG}
            count=0
            until grep -q 'installed successfully' {LOG} || [ "$count" -ge "{RETRY}" ]
            do
                sleep {WAIT}
                kubectl karmada  init --kubeconfig=/root/.kube/config \
                --wait-component-ready-timeout 60 \
                --crds {CRDS} 2>&1 | tee -a {LOG}
                count=$((count + 1))
                echo "-- try loop number: $count"
            done
            """,
            f"grep -q 'installed successfully' {LOG}",
            "cp -f /etc/karmada/karmada-apiserver.config ~/.kube/",
        ],
        _get_pty=True,
    )
    result = server.shell(
        name="Get members of Karmada.",
        commands=[
            "kubectl karmada --kubeconfig=/etc/karmada/karmada-apiserver.config get clusters",
        ],
    )
    python.call(
        name="Show members of Karmada.",
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
