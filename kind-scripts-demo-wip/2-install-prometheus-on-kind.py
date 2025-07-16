"""
Minimal recipe to deploy prometheus on kind on ubuntu server.

pyinfra -y -vv --user root ${SERVER_NAME} 2-install-prometheus-on-kind.py
"""

import io

from pyinfra.operations import files, python, server

from common import check_server, log_callback

# Note: Replace 127.0.0.1 with the actual IP address of your SMO service
SMO_URL = "http://127.0.0.1:8000/alerts"


PROM_VALUES_FILE = "prom-values.yaml"
PROM_VALUES_YAML = f"""\
prometheus:
  prometheusSpec:
    enableRemoteWriteReceiver: true
    scrapeInterval: 30s
    evaluationInterval: 30s
    externalLabels:
      cluster: kind-host
  service:
    nodePort: 30090
    type: NodePort
grafana:
  service:
    nodePort: 30080
    type: NodePort
defaultRules:
  create: false
  test-rules:
      groups:
      - name: smo-alerts
        rules: []
alertmanager:
  service:
    nodePort: 30093
    type: NodePort
  config:
    global:
      resolve_timeout: 5m
    receivers:
      - name: 'webhook-receiver'
        webhook_configs:
          # Note: Replace 127.0.0.1 with the actual IP address of your SMO service
          - url: '{SMO_URL}'
            send_resolved: false
    route:
      group_by: ['job']
      group_wait: 10s
      group_interval: 1m
      receiver: 'webhook-receiver'
      repeat_interval: 1m
      routes:
        - receiver: "webhook-receiver"
"""

PROM_NAMESPACE = "monitoring"
PROM_CLUSTER_NAME = "prom-cluster"
PROM_CONFIG_FILE = "prom-kins-config.yaml"
PROM_CONFIG = f"""\
 kind: Cluster
 apiVersion: kind.x-k8s.io/v1alpha4
 name: {PROM_CLUSTER_NAME}
 networking:
   apiServerAddress: "0.0.0.0" # Bind to all interfaces inside the container
   apiServerPort: 6444 # aka 6443 + 1
"""
PROM_KUBECONF_PATH = f"/root/.kube/{PROM_CLUSTER_NAME}.kubeconfig"


def main() -> None:
    install_prometheus()


def install_prometheus() -> None:
    add_prometheus_repo()
    put_prometheus_config_file()
    # remove_prior_prometheus_cluster()
    install_prometheus_cluster()


def add_prometheus_repo() -> None:
    REPO = "https://prometheus-community.github.io/helm-charts"
    server.shell(
        name="Add helm repo for prometheus",
        commands=[
            f"helm repo add prometheus-community {REPO}",
        ],
    )


def put_prometheus_config_file() -> None:
    files.put(
        name=f"Put file {PROM_VALUES_FILE!r}",
        src=io.StringIO(PROM_VALUES_YAML),
        dest=f"/root/{PROM_VALUES_FILE}",
    )


def remove_prior_prometheus_cluster() -> None:
    server.shell(
        name=f"Uninstall service prometheus {PROM_NAMESPACE!r}",
        commands=[
            f"helm uninstall prometheus -n {PROM_NAMESPACE}",
        ],
        _ignore_errors=True,
    )


def install_prometheus_cluster() -> None:
    files.put(
        name=f"Put file {PROM_CONFIG_FILE!r}",
        src=io.StringIO(PROM_CONFIG),
        dest=f"/root/{PROM_CONFIG_FILE}",
    )
    server.shell(
        name=f"Create kind cluster with name {PROM_CLUSTER_NAME!r}",
        commands=f"kind create cluster -n {PROM_CLUSTER_NAME} --config /root/{PROM_CONFIG_FILE}",
        _get_pty=True,
    )

    server.shell(
        name=f"Export confif {PROM_KUBECONF_PATH!r}",
        commands=(
            f"kind get kubeconfig --name {PROM_CLUSTER_NAME}  > {PROM_KUBECONF_PATH}"
        ),
        _get_pty=True,
    )

    server.shell(
        name=f"Join cluster {PROM_CLUSTER_NAME} to Karmada.",
        commands=(
            "kubectl karmada --kubeconfig /root/.kube/config "
            f"join {PROM_CLUSTER_NAME} "
            f"--cluster-kubeconfig={PROM_KUBECONF_PATH} "
            f'--cluster-context="kind-{PROM_CLUSTER_NAME}" '
        ),
        _get_pty=True,
    )

    server.shell(
        name=f"Waiting cluster {PROM_CLUSTER_NAME} ready",
        commands=(
            "kubectl -kubeconfig ~/.kube/config "
            "wait --for=condition=Ready "
            f'"cluster.cluster.karmada.io/{PROM_CLUSTER_NAME}" '
            "--timeout=5m"
        ),
        _get_pty=True,
    )

    server.shell(
        name=f"Install prometheus as {PROM_NAMESPACE!r}",
        commands=(
            f"helm install prometheus --create-namespace -n {PROM_NAMESPACE} "
            f"prometheus-community/kube-prometheus-stack --values {PROM_VALUES_FILE}"
        ),
    )
    result = server.shell(
        name=f"Show pods of {PROM_NAMESPACE!r}",
        commands=[
            f"kubectl get pods -n {PROM_NAMESPACE}",
        ],
    )
    python.call(
        name=f"Show pods of {PROM_NAMESPACE!r}",
        function=log_callback,
        result=result,
    )
    result = server.shell(
        name=f"Show joined of {PROM_NAMESPACE!r}",
        commands=[
            "kubectl karmada --kubeconfig ~/.kube/config get clusters",
        ],
    )
    python.call(
        name=f"Show joined of {PROM_NAMESPACE!r}",
        function=log_callback,
        result=result,
    )


main()
