"""
Minimal recipe to deploy karmada on members clusters.

# Note: to get the ip/url:
#     kubectl get svc -n karmada-system karmada-apiserver -o jsonpath='{.spec.clusterIP}:{.spec.ports[0].nodePort}'

pyinfra -y -vv --user root ${SERVER_NAME}  6-install-karmada-members.py

Notes:
Different address than the one provided by karmada splash screen:
KARMADA_API_SERVER_IP=$(docker inspect -f '{{.NetworkSettings.Networks.kind.IPAddress}}' karmada-host-control-plane)

Nephele command line
# Join Karmada
sudo karmadactl register $KARMADA_CONTROL_PLANE
    --token $KARMADA_TOKEN
    --discovery-token-ca-cert-hash $DISCOVERY_TOKEN_HASH
    --cluster-name $CLUSTER_ID
    --kubeconfig $KUBECONFIG

Some errors:

[preflight] Running pre-flight checks
error execution phase preflight: [preflight] Some fatal errors occurred:
        [ERROR]: karmada-system/karmada-agent-sa ServiceAccount already exists
        [ERROR]: karmada-system/karmada-agent Deployment already exists


error: invalid cluster name(member{mid}-control-plane): a lowercase RFC 1123 label must consist of lower case alphanumeric characters or '-', and must start and end with an alphanumeric character (e.g. 'my-name',  or '123-abc', regex used for validation is '[a-z0-9]([-a-z0-9]*[a-z0-9])?')


[nephele-jd] [preflight] Running pre-flight checks
    [nephele-jd] [preflight] All pre-flight checks were passed
    [nephele-jd] [karmada-agent-start] Waiting to perform the TLS Bootstrap
    [nephele-jd] error: couldn't validate the identity of the API Server: could not find a JWS signature in the cluster-info ConfigMap for token ID "t8xfio"

-> the bootstrap token (t8xfio.640u9gp9obc72v5d) you've been using has expired.

[nephele-jd] full address kubectl karmada register 172.20.0.3:6443 --token g9z4ta.0ofy85tj3hkdisxu --discovery-token-ca-cert-hash sha256:2077e2fb9522245eac09f146c06abb541935aefa4eb558dbc32fce19e8b1eb4d
    [nephele-jd] ADDRESS 172.20.0.3
    [nephele-jd] error: Missing or incomplete configuration info.  Please point to an existing, complete config file:
    [nephele-jd]   1. Via the command-line flag --kubeconfig
    [nephele-jd]   2. Via the KUBECONFIG environment variable
    [nephele-jd]   3. In your home directory as ~/.kube/config
    [nephele-jd] Error: executed 0 commands


[nephele-jd] error: couldn't validate the identity of the API Server: could not find a JWS signature in the cluster-info ConfigMap for token ID "7ge1s9"
    [nephele-jd] Error: executed 0 commands

"""

from textwrap import dedent

from pyinfra.operations import python, server

from common import log_callback


LOAD_K_CONFIG_CMD = (
    "export KUBECONFIG=/root/.kube/karmada.config:/root/.kube/members.config"
)
KINIT_LOG = "/root/log_karmada_init.txt"


def main() -> None:
    install_karmada_member(1)
    install_karmada_member(2)
    install_karmada_member(3)


def member_context_cmd(mid: int) -> str:
    return f"""
            {LOAD_K_CONFIG_CMD}
            kubectl config use-context member{mid}
            """
    # return f"""
    #         {LOAD_K_CONFIG_CMD}
    #         kubectl config use-context member{mid}
    #         """


def host_context_cmd() -> str:
    return f"""
            {LOAD_K_CONFIG_CMD}
            kubectl config use-context karmada-host
            """


def install_karmada_member(mid: int):
    use_ctx = member_context_cmd(1)
    host_ctx = host_context_cmd()

    result = server.shell(
        name=f"Check member{mid} nodes",
        commands=[
            dedent(f"""\
            {use_ctx}
            kubectl get nodes
            """)
        ],
    )
    python.call(
        name=f"Show member{mid} nodes",
        function=log_callback,
        result=result,
    )

    # server.shell(
    #     name="Uninstall any prior prometheus monitoring",
    #     commands=[
    #         dedent(f"""\
    #         {use_ctx}
    #         helm uninstall prometheus-member{mid} -n monitoring
    #         kubectl delete namespace monitoring
    #         """),
    #     ],
    #     _ignore_errors=True,
    # )

    cmd = (
        host_ctx
        + "FULLADDR=$(kubectl karmada token create --print-register-command --kubeconfig=/root/.kube/karmada.config)\n"
        + use_ctx
        + "ADDRESS=$(docker inspect -f '{{.NetworkSettings.Networks.kind.IPAddress}}' karmada-host-control-plane)\n"
        + f"""
        echo "full address $FULLADDR"
        #MODIFIED_FULLADDR=$(echo "$FULLADDR" | sed -E 's/:[0-9]{{4}} /:5443 /')
        #echo "modified full address $MODIFIED_FULLADDR"

        echo "ADDRESS $ADDRESS"
        echo "karmada-host-control-plane port is:"
        docker port karmada-host-control-plane

        KUBECONFIG=/root/.kube/members.config
        kubectl config use-context member{mid}
        #$MODIFIED_FULLADDR --cluster-name member{mid} --kubeconfig /root/.kube/members.config
        #$FULLADDR --cluster-name member{mid}-control-plane --kubeconfig /root/.kube/members.config
        $FULLADDR --cluster-name member{mid} --kubeconfig /root/.kube/members.config
        """
        # + "ADDRESS=$(docker inspect -f '{{.NetworkSettings.Networks.kind.IPAddress}}' karmada-host-control-plane)\n"
        # + f'LINE=$(grep -m 1 "discovery-token-ca-cert" {KINIT_LOG})\n'
        # + f"""
        # ADDRESS=$( echo $LINE | awk '{{print $4}}' )
        # TOKEN=$( echo $LINE | awk '{{print $6}}' )
        # DISCOVERY_TOKEN=$( echo $LINE | awk '{{print $8}}' )
        # echo $KUBECONFIG
        # echo $ADDRESS
        # echo $TOKEN $DISCOVERY_TOKEN member{mid}-control-pane
        # kubectl karmada register $ADDRESS
        # kubectl karmada register $ADDRESS:5443 \
        # --token $TOKEN \
        # --discovery-token-ca-cert-hash $DISCOVERY_TOKEN \
        # --cluster-name member{mid}-control-plane
        # --cluster-name member{mid}
        # """
    )

    server.shell(
        # or maybe: KARMADA_API_SERVER_IP=$(docker inspect -f '{{.NetworkSettings.Networks.kind.IPAddress}}' karmada-host-control-plane)
        name=f"Install Karmada on member{mid}",
        commands=cmd,
        _shell_executable="/bin/bash",
    )

    result = server.shell(
        name=f"Check member{mid} pods",
        commands=[
            dedent(f"""\
            {use_ctx}
            kubectl get pods
            """)
        ],
    )
    python.call(
        name=f"Show member{mid} pods",
        function=log_callback,
        result=result,
    )

    result = server.shell(
        name="Check kubectl get clusters",
        commands=[
            dedent(f"""\
                {host_ctx}

                kubectl get clusters
            """)
        ],
    )
    python.call(
        name="Show kubectl get clusters",
        function=log_callback,
        result=result,
    )


main()
