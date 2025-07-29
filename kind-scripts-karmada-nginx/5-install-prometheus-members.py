"""
Minimal recipe to deploy prometheus on members clusters.

# Note: to get the ip/url:
#     kubectl get svc -n karmada-system karmada-apiserver -o jsonpath='{.spec.clusterIP}:{.spec.ports[0].nodePort}'

pyinfra -y -vv --user root ${SERVER_NAME}  5-install-prometheus-members.py


export KUBECONFIG=/root/.kube/karmada.config:/root/.kube/members.config:~/.kube/config
kubectl config use-context member1
kubectl get nodes

kubectl create namespace monitoring
helm repo add prometheus-community https://prometheus-community.github.io/helm-charts
helm repo update

create prometheus-member1-values.yaml

helm install prometheus-member1 prometheus-community/prometheus -n monitoring -f prometheus-member1-values.yaml

kubectl get pods -n monitoring

 docker inspect -f '{{.NetworkSettings.Networks.kind.IPAddress}}' member1-control-plane
172.20.0.2
-> 172.20.0.2:3001
"""

from textwrap import dedent

from pyinfra.operations import python, server

from common import log_callback

# CLUSTER_NAME = "karmada-host"  # or member1 ?
# CENTRAL_PROMETHEUS_IP_AND_PORT = "127.0.0.1:30093"

# for nephele, nedd first the source: <CLUSTER_NAME> ans <CENTRAL_PROMETHEUS_IP_AND_PORT>

PROMETHEUS_REPO = "https://prometheus-community.github.io/helm-charts"

# LOAD_K_CONFIG_CMD = "export KUBECONFIG=/root/.kube/karmada.config:/root/.kube/members.config:~/.kube/config"
LOAD_K_CONFIG_CMD = (
    "export KUBECONFIG=/root/.kube/karmada.config:/root/.kube/members.config"
)


def main() -> None:
    install_prometheus_member(1)


def member_context_cmd(mid: int) -> str:
    return f"""
            {LOAD_K_CONFIG_CMD}
            kubectl config use-context member{mid}
            """


def nodeport(mid: int) -> int:
    return 30000 + mid


def install_prometheus_member(mid: int):
    use_ctx = member_context_cmd(1)

    result = server.shell(
        name=f"Check member{mid} nodes",
        commands=[
            dedent(f"""\
            {use_ctx}

            kubectl get nodes
            """)
        ],
        _shell_executable="/bin/bash",
        _get_pty=True,
    )
    python.call(
        name=f"Show member{mid} nodes",
        function=log_callback,
        result=result,
    )

    server.shell(
        name="Uninstall any prior prometheus monitoring",
        commands=[
            dedent(f"""\
            {use_ctx}

            helm uninstall prometheus-member{mid} -n monitoring
            kubectl delete namespace monitoring
            """),
        ],
        _ignore_errors=True,
        _shell_executable="/bin/bash",
        _get_pty=True,
    )

    server.shell(
        name=f"Create namespace monitoring for member{mid}",
        commands=[
            dedent(f"""\
            {use_ctx}

            kubectl create namespace monitoring
            """)
        ],
        _shell_executable="/bin/bash",
        _get_pty=True,
    )

    server.shell(
        name=f"Add helm repo for prometheus for member{mid}",
        commands=[
            dedent(f"""\
            {use_ctx}

            helm repo add prometheus-community {PROMETHEUS_REPO}
            helm repo update
            """)
        ],
        _shell_executable="/bin/bash",
        _get_pty=True,
    )

    server.shell(
        name=f"Build Prometheus config for member{mid}",
        commands=[
            dedent("""\
            export KUBECONFIG=/root/.kube/karmada.config:/root/.kube/members.config
            kubectl config use-context member1

            central_ip=$(kubectl get nodes -o jsonpath='{.items[0].status.addresses[?(@.type=="InternalIP")].address}')
            central_port=$(kubectl -n monitoring get svc prometheus-kube-prometheus-prometheus -o jsonpath='{.spec.ports[0].nodePort}')

            cat << EOF > /root/prometheus-member1-values.yaml
            # prometheus-member-values.yaml
            prometheus:
              prometheusSpec:
                externalLabels:
                  source: member1
                scrapeInterval: 30s
                remoteWrite:
                  - url: "http://${central_ip}:${central_port}/api/v1/write"
              service:
                type: NodePort
                nodePort: 30101
            EOF
            """)
        ],
        _shell_executable="/bin/bash",
        _get_pty=True,
    )

    server.shell(
        name=f"Install Prometheus stack for member{mid}",
        commands=[
            dedent(f"""\
            {use_ctx}

            helm install prometheus-member{mid} \
            --create-namespace -n monitoring \
            prometheus-community/prometheus \
            --values /root/prometheus-member1-values.yaml
            """)
            # "helm install prometheus --create-namespace -n monitoring "
            # "prometheus-community/kube-prometheus-stack "
            # "--values /root/{PROM_VALUES_FILE}"
        ],
        _shell_executable="/bin/bash",
        _get_pty=True,
    )

    result = server.shell(
        name=f"Check member{mid} monitoring pods",
        commands=[
            dedent(f"""\
            {use_ctx}
            kubectl get pods -n monitoring
            """)
        ],
    )
    python.call(
        name=f"Show member{mid} monitoring pods",
        function=log_callback,
        result=result,
    )

    result = server.shell(
        name=f"Check member{mid} docker IP",
        commands=[
            dedent("""\
                docker inspect -f '{{.NetworkSettings.Networks.kind.IPAddress}}' \
                member1-control-plane
            """)
        ],
    )
    python.call(
        name=f"smke test 1: show member{mid} docker IP",
        function=log_callback,
        result=result,
    )

    result = server.shell(
        name=f"Check member{mid} pods",
        commands=[
            dedent(f"""\
                {use_ctx}
                kubectl -n monitoring get pods | grep prometheus
            """)
        ],
        _shell_executable="/bin/bash",
        _get_pty=True,
    )
    python.call(
        name=f"smke test 2: show member{mid} prometheus pods",
        function=log_callback,
        result=result,
    )

    result = server.shell(
        name=f"Check member{mid} services",
        commands=[
            dedent(f"""\
                {use_ctx}

                kubectl -n monitoring get svc prometheus-member1-server
            """)
        ],
        _shell_executable="/bin/bash",
        _get_pty=True,
    )
    python.call(
        name=f"smke test 3: show member{mid} services",
        function=log_callback,
        result=result,
    )

    result = server.shell(
        name=f"Check member{mid} services",
        commands=[
            dedent(f"""\
                {use_ctx}

                kubectl -n monitoring get svc prometheus-member1-server
            """)
        ],
        _shell_executable="/bin/bash",
        _get_pty=True,
    )
    python.call(
        name=f"smke test 4: show member{mid} services",
        function=log_callback,
        result=result,
    )

    # result = server.shell(
    #     name=f"Check member{mid} services",
    #     commands=[
    #         dedent("""\
    #             export KUBECONFIG=/root/.kube/karmada.config:/root/.kube/members.config
    #             kubectl config use-context member1

    #             member1_node_ip=$(kubectl -n monitoring get nodes -o jsonpath='{.items[0].status.addresses[?(@.type=="InternalIP")].address}')
    #             echo "http://${member1_node_ip}:30101"
    #         """)
    #     ],
    #     _shell_executable="/bin/bash",
    #     _get_pty=True,
    # )
    # python.call(
    #     name=f"smke test 5: show member{mid} node ip port",
    #     function=log_callback,
    #     result=result,
    # )

    result = server.shell(
        name=f"Check member{mid} access from inner cluster",
        commands=[
            dedent("""\
                export KUBECONFIG=/root/.kube/karmada.config:/root/.kube/members.config
                kubectl config use-context member1

                sleep 5

                kubectl -n monitoring run -i --tty --rm debug \
                --image=busybox --restart=Never \
                -- wget -qO- http://prometheus-member1-server:80 | head -n10
            """)
        ],
        _shell_executable="/bin/bash",
        _get_pty=True,
    )
    python.call(
        name=f"smke test 5: show member{mid} access from inner cluster",
        function=log_callback,
        result=result,
    )


main()
