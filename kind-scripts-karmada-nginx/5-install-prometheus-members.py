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

import io
from textwrap import dedent

from pyinfra.operations import files, python, server

from common import log_callback

PROM_MEMBER_YML = """\
# prometheus-member-values.yaml
server:
  service:
    type: NodePort
    nodePort: %s # 30001 for member1,...
    targetPort: 9090

  configFlags:
    config.file: /etc/prometheus/prometheus.yml

  extraConfigmapMounts:
    - name: prometheus-config
      mountPath: /etc/prometheus/prometheus.yml
      subPath: prometheus.yml
      configMap: prometheus-member-config

configMaps:
  prometheus-member-config:
    prometheus.yml: |
      global:
        scrape_interval: 15s
        evaluation_interval: 15s

      scrape_configs:
        - job_name: 'prometheus'
          static_configs:
            - targets: ['localhost:9090'] # Scrape itself
        - job_name: 'kubernetes-nodes'
          kubernetes_sd_configs:
          - role: node
          relabel_configs:
          - action: labelmap
            regex: __meta_kubernetes_node_label_(.+)
          - target_label: __address__
            replacement: kubernetes.default.svc:443
          - source_labels: [__meta_kubernetes_node_name]
            regex: (.+)
            target_label: __metrics_path__
            replacement: /api/v1/nodes/${1}/proxy/metrics
          scheme: https
          tls_config:
            insecure_skip_verify: true
          bearer_token_file: /var/run/secrets/kubernetes.io/serviceaccount/token
        - job_name: 'kubernetes-pods'
          kubernetes_sd_configs:
          - role: pod
          relabel_configs:
          - source_labels: [__meta_kubernetes_pod_annotation_prometheus_io_scrape]
            action: keep
            regex: true
          - source_labels: [__meta_kubernetes_pod_annotation_prometheus_io_path]
            action: replace
            target_label: __metrics_path__
            regex: (.+)
          - source_labels: [__address__, __meta_kubernetes_pod_annotation_prometheus_io_port]
            action: replace
            regex: ([^:]+)(?::\d+)?;(\d+)
            replacement: $1:$2
            target_label: __address__
          - action: labelmap
            regex: __meta_kubernetes_pod_label_(.+)
          - source_labels: [__meta_kubernetes_namespace]
            action: replace
            target_label: kubernetes_namespace
          - source_labels: [__meta_kubernetes_pod_name]
            action: replace
            target_label: kubernetes_pod_name
"""

# for nephele, nedd first the source: <CLUSTER_NAME> ans <CENTRAL_PROMETHEUS_IP_AND_PORT>
PROM_MEMBER_YML_NEPHELE = """\
# prometheus-member-values.yaml
prometheus:
  prometheusSpec:
    externalLabels:
      source: %s
    scrapeInterval: 30s
    remoteWrite:
      - url: "http://%s/api/v1/write"

  service:
    type: NodePort
    nodePort: %s
"""

PROMETHEUS_REPO = "https://prometheus-community.github.io/helm-charts"

# LOAD_K_CONFIG_CMD = "export KUBECONFIG=/root/.kube/karmada.config:/root/.kube/members.config:~/.kube/config"
LOAD_K_CONFIG_CMD = (
    "export KUBECONFIG=/root/.kube/karmada.config:/root/.kube/members.config"
)


def main() -> None:
    install_prometheus_member(1)
    # install_prometheus_member(2)
    install_prometheus_member(3)


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
    )

    server.shell(
        name=f"Create namespace monitoring for member{mid}",
        commands=[
            dedent(f"""\
            {use_ctx}
            kubectl create namespace monitoring
            """)
        ],
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
    )

    file_name = f"prometheus-member{mid}-values.yaml"
    file_content = PROM_MEMBER_YML % nodeport(mid)
    files.put(
        name=f"Put prometheus config file {file_name}",
        src=io.StringIO(file_content),
        dest=f"/root/{file_name}",
    )

    server.shell(
        name=f"Install Prometheus stack for member{mid}",
        commands=[
            dedent(f"""\
            {use_ctx}
            helm install prometheus-member{mid} \
            prometheus-community/prometheus \
            -n monitoring \
            -f /root/{file_name}
            """)
            # "helm install prometheus --create-namespace -n monitoring "
            # "prometheus-community/kube-prometheus-stack "
            # "--values /root/{PROM_VALUES_FILE}"
        ],
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
            dedent(f"""\
                docker inspect -f '{{.NetworkSettings.Networks.kind.IPAddress}}' member{mid}-control-plane
            """)
        ],
    )
    python.call(
        name=f"Show member{mid} docker IP",
        function=log_callback,
        result=result,
    )


main()
