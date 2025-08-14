"""
Minimal recipe to deploy prometheus on members clusters.

# Note: to get the ip/url:
#     kubectl get svc -n karmada-system karmada-apiserver -o jsonpath='{.spec.clusterIP}:{.spec.ports[0].nodePort}'

pyinfra -y -vv --user root ${SERVER_NAME}  6-install-prometheus-members.py


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

# CENTRAL_PROMETHEUS_IP_AND_PORT = "127.0.0.1:30093"

# for nephele, nedd first the source: <CLUSTER_NAME> ans <CENTRAL_PROMETHEUS_IP_AND_PORT>

PROMETHEUS_REPO = "https://prometheus-community.github.io/helm-charts"


def main() -> None:
    for mid in (1, 2):
        install_prometheus_member(mid)
        install_prometheus_crds_member(mid)
        check_prometheus_member(mid)


def member_context_cmd(mid: int) -> str:
    return f"""
            export KUBECONFIG="/root/.kube/karmada-apiserver.config"
            kubectl config use-context member{mid}
            """


def nodeport(mid: int) -> int:
    return 30090 + mid


def install_prometheus_member(mid: int):
    member_ctx = member_context_cmd(mid)
    port = nodeport(mid)

    result = server.shell(
        name=f"Check member{mid} nodes",
        commands=[
            dedent(f"""\
            {member_ctx}

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
        name=f"Uninstall any prior prometheus monitoring for member{mid}",
        commands=[
            dedent(f"""\
            {member_ctx}

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
            {member_ctx}

            kubectl create namespace monitoring || true
            """)
        ],
        _shell_executable="/bin/bash",
        _get_pty=True,
    )

    server.shell(
        name=f"Add helm repo for prometheus for member{mid}",
        commands=[
            dedent(f"""\
            {member_ctx}

            helm repo add prometheus-community {PROMETHEUS_REPO}
            helm repo update
            """)
        ],
        _shell_executable="/bin/bash",
        _get_pty=True,
    )

    result = server.shell(
        name=f"Build Prometheus config for member{mid}",
        commands=[
            dedent(f"""\
            export KUBECONFIG="/root/.kube/karmada-apiserver.config"
            kubectl config use-context karmada-host

            central_ip=$(kubectl get nodes -o jsonpath='{{.items[0].status.addresses[?(@.type=="InternalIP")].address}}')

            #central_port=$(kubectl -n monitoring get svc prometheus-kube-prometheus-prometheus -o jsonpath='{{.spec.ports[0].nodePort}}')
            # always 30090

            cat << EOF > /root/prometheus-member{mid}-values.yaml
            # prometheus-member{mid}-values.yaml
            prometheus:
              prometheusSpec:
                externalLabels:
                  source: member{mid}
                scrapeInterval: 30s
                remoteWrite:
                  - url: "http://${{central_ip}}:30090/api/v1/write"
              service:
                nodePort: {port}
                type: NodePort
            EOF

            cat /root/prometheus-member{mid}-values.yaml
            """)
        ],
        _shell_executable="/bin/bash",
        _get_pty=True,
    )
    python.call(
        name=f"Show member{mid} NodePort type",
        function=log_callback,
        result=result,
    )

    server.shell(
        name=f"Install Prometheus stack for member{mid}",
        commands=[
            dedent(f"""\
            {member_ctx}

            helm install prometheus-member{mid} \
            --create-namespace -n monitoring \
            prometheus-community/prometheus \
            --values /root/prometheus-member{mid}-values.yaml
            """)
            # "helm install prometheus --create-namespace -n monitoring "
            # "prometheus-community/kube-prometheus-stack "
            # "--values /root/{PROM_VALUES_FILE}"
        ],
        _shell_executable="/bin/bash",
        _get_pty=True,
    )

    result = server.shell(
        name=f"Fix member{mid} nodeport type",
        commands=[
            dedent(f"""\
            {member_ctx}

            kubectl get svc prometheus-member{mid}-server -n monitoring \
            -o yaml > /root/prometheus-svc-{mid}-backup-before.yaml

            kubectl patch svc prometheus-member{mid}-server -n monitoring \
            --type='json' \
            -p='[{{"op":"replace","path":"/spec/type","value":"NodePort"}},\
            {{"op":"replace","path":"/spec/ports/0/nodePort","value":{port}}}]'

            kubectl get svc prometheus-member{mid}-server -n monitoring \
            -o yaml > /root/prometheus-svc-{mid}-backup-after.yaml
            """)
        ],
    )

    result = server.shell(
        name=f"Check member{mid} NodePort type",
        commands=[
            dedent(f"""\
            {member_ctx}

            kubectl get svc prometheus-member{mid}-server -n monitoring
            echo "pods:"
            kubectl -n monitoring get pods
            echo "services:"
            kubectl -n monitoring get svc
            """)
        ],
    )
    python.call(
        name=f"Show member{mid} NodePort type",
        function=log_callback,
        result=result,
    )


def install_prometheus_crds_member(mid: int) -> None:
    member_ctx = member_context_cmd(mid)
    # Base URL for the Prometheus Operator CRDs
    BASE_URL = (
        "https://raw.githubusercontent.com/prometheus-operator/"
        "prometheus-operator/v0.84.1/example/prometheus-operator-crd"
    )

    result = server.shell(
        name=f"Install monitoring CRDs for member{mid}",
        commands=[
            f"""
            {member_ctx}

            kubectl apply --server-side -f {BASE_URL}/monitoring.coreos.com_alertmanagerconfigs.yaml
            kubectl apply --server-side -f {BASE_URL}/monitoring.coreos.com_alertmanagers.yaml
            kubectl apply --server-side -f {BASE_URL}/monitoring.coreos.com_podmonitors.yaml
            kubectl apply --server-side -f {BASE_URL}/monitoring.coreos.com_probes.yaml
            kubectl apply --server-side -f {BASE_URL}/monitoring.coreos.com_prometheusagents.yaml
            kubectl apply --server-side -f {BASE_URL}/monitoring.coreos.com_prometheuses.yaml
            kubectl apply --server-side -f {BASE_URL}/monitoring.coreos.com_prometheusrules.yaml
            kubectl apply --server-side -f {BASE_URL}/monitoring.coreos.com_scrapeconfigs.yaml
            kubectl apply --server-side -f {BASE_URL}/monitoring.coreos.com_servicemonitors.yaml
            kubectl apply --server-side -f {BASE_URL}/monitoring.coreos.com_thanosrulers.yaml
            """
        ],
        _shell_executable="/bin/bash",
    )
    python.call(
        name=f"Show installed monitoring CRDs for member{mid}",
        function=log_callback,
        result=result,
    )


def check_prometheus_member(mid: int) -> None:
    member_ctx = member_context_cmd(mid)
    port = nodeport(mid)

    result = server.shell(
        name=f"Check member{mid} docker IP",
        commands=[
            dedent(f"""\
                docker inspect -f '{{{{.NetworkSettings.Networks.kind.IPAddress}}}}' \
                member{mid}-control-plane
            """)
        ],
    )
    python.call(
        name=f"Smoke test 1: show member{mid} docker IP",
        function=log_callback,
        result=result,
    )

    result = server.shell(
        name=f"Check member{mid} prometheus service",
        commands=[
            dedent(f"""\
                {member_ctx}

                kubectl -n monitoring get svc prometheus-member{mid}-server
            """)
        ],
        _shell_executable="/bin/bash",
        _get_pty=True,
    )
    python.call(
        name=f"Smoke test 2: show member{mid} services",
        function=log_callback,
        result=result,
    )

    result = server.shell(
        name=f"Check member{mid} access from outer cluster",
        commands=[
            dedent(
                """\
                export KUBECONFIG="/root/.kube/karmada-apiserver.config"
                """
                f"""
                kubectl config use-context member{mid}
                """
                """
                member_node_ip=$(kubectl get nodes -o \
                jsonpath='{.items[0].status.addresses[?(@.type=="InternalIP")].address}')

                """
                f"""
                url="http://${{member_node_ip}}:{port}"
                """
                """

                max_try=30
                interval=2
                for ((i=1; i<=max_try; i++)); do
                  echo "try ${url} (attempt $i)..."
                  if curl -s ${url} > /dev/null; then
                    break
                  else
                    sleep $interval
                  fi
                done
                curl -sS ${url} 2>&1 | head -n5
            """
            )
        ],
        _shell_executable="/bin/bash",
        _get_pty=True,
    )
    python.call(
        name=f"Smoke test 3: member{mid} access from outer cluster",
        function=log_callback,
        result=result,
    )

    result = server.shell(
        name=f"Check member{mid} access from inner cluster",
        commands=[
            dedent(f"""\
                export KUBECONFIG="/root/.kube/karmada-apiserver.config"
                kubectl config use-context member{mid}

                sleep 20

                kubectl -n monitoring run -i --tty --rm debug \
                --image=busybox --restart=Never \
                -- sh -c 'i=0; while [ $i -lt 10 ]; do \
                wget -qO- http://prometheus-member{mid}-server:80 2>/dev/null \
                && break; i=$((i+1)); sleep 2; done | head -n10'
            """)
        ],
        _shell_executable="/bin/bash",
        _get_pty=True,
    )
    python.call(
        name=f"Smoke test 4: show member{mid} access from inner cluster",
        function=log_callback,
        result=result,
    )


main()
