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
HOST_CONFIG_FILENAME = "host.kubeconfig"
KUBE_CONF_DIR = "/root/.kube"
HOST_CONF_PATH = f"{KUBE_CONF_DIR}/{HOST_CONFIG_FILENAME}"
KUBECONFIG = HOST_CONF_PATH
HOST_CONTEXT = "kind-host"


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
                kubectl karmada  init \
                --kubeconfig={KUBECONFIG} \
                --context={HOST_CONTEXT} \
                --wait-component-ready-timeout 60 \
                --crds {CRDS} 2>&1 | tee -a {LOG}
                count=$((count + 1))
                echo "-- try loop number: $count"
            done
            """,
            f"grep -q 'installed successfully' {LOG}",
            "cp -f /etc/karmada/karmada-apiserver.config /root/.kube/",
        ],
        _get_pty=True,
    )

    # server.shell(
    #     name="Create a token",
    #     commands=[
    #         (
    #             "kubectl karmada token create --ttl 0 --print-register-command "
    #             "--kubeconfig /etc/karmada/karmada-apiserver.config"
    #         ),
    #         "cp -f /etc/karmada/karmada-apiserver.config /root/.kube/",
    #     ],
    #     _get_pty=True,
    # )
    #
    result = server.shell(
        name="Get Karmada Control Plane",
        commands=[
            (
                f"kubectl --kubeconfig={KUBECONFIG} "
                f"--context={HOST_CONTEXT} "
                " get pods -n karmada-system"
            ),
        ],
    )
    python.call(
        name="Show Karmada Control Plane",
        function=log_callback,
        result=result,
    )

    result = server.shell(
        name="Get Karmada all pods",
        commands=[
            f"kubectl --kubeconfig={KUBECONFIG} get pods --all-namespaces",
        ],
    )
    python.call(
        name="Show Karmada all pods",
        function=log_callback,
        result=result,
    )

    # result = server.shell(
    #     name="Get members of Karmada.",
    #     commands=[
    #         (
    #             "kubectl karmada "
    #             "--kubeconfig=/root/.kube/karmada-apiserver.config "
    #             "get clusters"
    #         ),
    #     ],
    # )
    # python.call(
    #     name="Show members of Karmada.",
    #     function=log_callback,
    #     result=result,
    # )


main()
