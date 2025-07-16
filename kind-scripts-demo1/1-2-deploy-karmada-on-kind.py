"""
Minimal recipe to deploy kind kubernetes engine and tools on a ubuntu like distribution.

pyinfra -y -vv --user root ${SERVER_NAME} 1-2-deploy-karmada-on-kind.py
"""

import io
from pyinfra import host
from pyinfra.facts.files import File
from pyinfra.operations import apt, files, python, server, snap, systemd

from common import check_server, log_callback

# python.call(name=" ", function=log_callback, result=result)

K_CLUSTER_NAME = "karmada-cluster"
KARMADA_CONFIG_FILE = "karmada-kind-config.yaml"
KARMADA_CONFIG = f"""\
 kind: Cluster
 apiVersion: kind.x-k8s.io/v1alpha4
 name: {K_CLUSTER_NAME}
 networking:
   apiServerAddress: "0.0.0.0"
   apiServerPort: 6443
"""
KARMADA_KUBECONFIG_FILE = "/root/.kube/${K_CLUSTER_NAME}.kubeconfig"
KARMADA_SYSTEM_NAMESPACE = "karmada-system"


def main() -> None:
    create_kind_karmada_cluster()
    init_karmada_configuration()


def create_kind_karmada_cluster():
    files.put(
        name=f"Put file {KARMADA_CONFIG_FILE!r}",
        src=io.StringIO(KARMADA_CONFIG),
        dest=f"/root/{KARMADA_CONFIG_FILE}",
    )
    server.shell(
        name=f"Create kind cluster with name {K_CLUSTER_NAME!r}",
        commands=f"kind create cluster -n {K_CLUSTER_NAME} --config /root/{KARMADA_CONFIG_FILE}",
        _get_pty=True,
    )
    # server.shell(
    #     name=f"Copy config in /root/.kube/{KARMADA_KUBECONFIG_FILE}",
    #     commands=f"kind get kubeconfig --name {K_CLUSTER_NAME} > {KARMADA_KUBECONFIG_FILE}",
    #     _get_pty=True,
    # )

    result = server.shell(
        name="Show cluster info",
        commands=[
            # f"kubectl cluster-info --context kind-{NAME}",
            "kubectl cluster-info --kubeconfig ~/.kube/config",
        ],
    )
    python.call(
        name="Show cluster info",
        function=log_callback,
        result=result,
    )

    # result = server.shell(
    #     name="Show cluster info 2",
    #     commands=[
    #         # f"kubectl cluster-info --context kind-{NAME}",
    #         f"kubectl cluster-info --kubeconfig {KARMADA_KUBECONFIG_FILE}",
    #     ],
    # )
    # python.call(
    #     name="Show cluster info2",
    #     function=log_callback,
    #     result=result,
    # )


def init_karmada_configuration():
    VERSION = "v1.14.1"
    CRDS = (
        f"https://github.com/karmada-io/karmada/releases/download/{VERSION}/crds.tar.gz"
    )
    LOG = "/root/log_karmada_init.txt"
    RETRY = 24  # 4 min
    WAIT = 10
    # server.shell(
    #     name="Remove old karmada configuration if needed",
    #     commands="kubectl karmada deinit --purge-namespace || true",
    #     # "rm -fr /var/lib/karmada-etcd ",
    # )

    server.shell(
        name="Install karmada configuration",
        commands=[
            f"""
            echo "" > {LOG}
            count=0
            until grep -q 'installed successfully' {LOG} || [ "$count" -ge "{RETRY}" ]
            do
                sleep {WAIT}
                kubectl karmada --kubeconfig ~/.kube/config init \
                --wait-component-ready-timeout 60 \
                --crds {CRDS} 2>&1 | tee {LOG}
                count=$((count + 1))
                echo "-- try loop number: $count"
            done
            """,
            f"grep -q 'installed successfully' {LOG}",
            "cp -f /etc/karmada/karmada-apiserver.config ~/.kube/",
        ],
        _get_pty=True,
    )
    # server.shell(
    #     name="Wait status ready",
    #     commands=[
    #         (
    #             "kubectl --kubeconfig ~/.kube/config wait "
    #             "--for=condition=Ready pods -l app.kubernetes.io/part-of=karmada "
    #             f"-n {KARMADA_SYSTEM_NAMESPACE} --timeout=5m"
    #         )
    #     ],
    # )
    result = server.shell(
        name="Show cluster info",
        commands=[
            "kubectl cluster-info --kubeconfig ~/.kube/config",
        ],
    )
    python.call(
        name="Show cluster info",
        function=log_callback,
        result=result,
    )


#     result = server.shell(
#         name="Show pods of karmada-system",
#         commands=[
#             "kubectl get pods -n karmada-system",
#         ],
#     )
#     python.call(
#         name="Show pods of karmada-system",
#         function=log_callback,
#         result=result,
#     )


main()
