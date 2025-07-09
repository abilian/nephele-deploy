"""
Minimal recipe to deploy prometheus on kind on ubuntu server.

pyinfra -y -vv --user root HOST 2-install-prometheus-on-kind.py
"""

import io

from pyinfra.operations import files, python, server

from common import check_server, log_callback

PROM_NAME = "monitoring"
PROM_VALUES_FILE = "prom-values.yaml"
PROM_VALUES_YAML = """\
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
          - url: 'http://127.0.0.1:8000/alerts'
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


def main() -> None:
    check_server()
    install_prometheus()


def install_prometheus() -> None:
    add_prometheus_repo()
    put_prometheus_config_file()
    remove_prior_prometheus_cluster()
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
        name=f"Uninstall service prometheus {PROM_NAME!r}",
        commands=[
            f"helm uninstall prometheus -n {PROM_NAME}",
        ],
        _ignore_errors=True,
    )


def install_prometheus_cluster() -> None:
    server.shell(
        name=f"Install prometheus as {PROM_NAME!r}",
        commands=(
            f"helm install prometheus --create-namespace -n {PROM_NAME} "
            f"prometheus-community/kube-prometheus-stack --values {PROM_VALUES_FILE}"
        ),
    )
    result = server.shell(
        name=f"Show pods of {PROM_NAME!r}",
        commands=[
            f"kubectl get pods -n {PROM_NAME}",
        ],
    )
    python.call(
        name=f"Show pods of {PROM_NAME!r}",
        function=log_callback,
        result=result,
    )


main()
