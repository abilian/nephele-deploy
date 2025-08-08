"""
Minimal recipe to deploy prometheus on kind on ubuntu server.

Based on:
https://gitlab.eclipse.org/eclipse-research-labs/nephele-project/nephele-platform


--> Starting operation: Install kube prometheus stack
[nephele-jd] >>> sh -c 'helm install prometheus --create-namespace -n monitoring prometheus-community/kube-prometheus-stack --values /root/prom-values.yaml'
    [nephele-jd] Error: INSTALLATION FAILED: Kubernetes cluster unreachable: Get "http://localhost:8080/version": dial tcp [::1]:8080: connect: connection refused
    [nephele-jd] Error: executed 0 commands


Note: to get the ip/url:
    kubectl get svc -n karmada-system karmada-apiserver -o jsonpath='{.spec.clusterIP}:{.spec.ports[0].nodePort}'

pyinfra -y -vv --user root ${SERVER_NAME} 5-install-prometheus.py
"""

import io
from pyinfra.operations import files, python, server

from common import log_callback


# Note: Replace 127.0.0.1 with the actual IP address of your SMO service

# assuming installtion where we have control plane installed on karmada-host:
# # kubectl config get-contexts
# CURRENT   NAME                CLUSTER             AUTHINFO            NAMESPACE
# *         karmada-apiserver   karmada-apiserver   karmada-apiserver
#           karmada-host        kind-karmada-host   kind-karmada-host

CLUSTER_NAME = "karmada-host"
KCONFIG = "/root/.kube/karmada-apiserver.config"
# Define the Prometheus Operator version
# VERSION = "v0.78.2"
# Base URL for the Prometheus Operator CRDs
# BASE_URL = (
#     "https://raw.githubusercontent.com/prometheus-operator/"
#     f"prometheus-operator/{VERSION}/example/prometheus-operator-crd"
# )

# Kubeconfig file of the Karmada control plane
# KUBECONFIG = "/root/.kube/karmada-apiserver.config"

# SMO beeing installed later...
SMO_URL = "http://127.0.0.1:8000/alerts"


PROM_VALUES_FILE = "prom-values.yaml"
# from https://gitlab.eclipse.org/eclipse-research-labs/nephele-project/nephele-platform
PROM_VALUES_YAML = f"""\
prometheus:
  prometheusSpec:
    enableRemoteWriteReceiver: true
    scrapeInterval: 30s
    evaluationInterval: 30s
    externalLabels:
      cluster: {CLUSTER_NAME}
  service:
    nodePort: 30090
    type: NodePort
defaultRules:
  create: false
additionalPrometheusRulesMap:
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
grafana:
  service:
    type: NodePort
    nodePort: 30002
"""


def main() -> None:
    remove_prior_prometheus_cluster()
    add_prometheus_repo()
    put_prometheus_config_file()
    install_kube_prometheus_stack_v3()
    install_service_monitor_crds_in_api_server()


def remove_prior_prometheus_cluster() -> None:
    server.shell(
        name="Uninstall service prometheus monitoring",
        commands=[
            f"""
            export KUBECONFIG="{KCONFIG}"
            kubectl config use-context karmada-host

            helm uninstall prometheus -n monitoring
            """
        ],
        _ignore_errors=True,
        _shell_executable="/bin/bash",
    )


def add_prometheus_repo() -> None:
    REPO = "https://prometheus-community.github.io/helm-charts"
    server.shell(
        name="Add helm repo for prometheus",
        commands=[
            f"""
            export KUBECONFIG="{KCONFIG}"
            kubectl config use-context karmada-host

            helm repo add prometheus-community {REPO}
            helm repo update
            """,
        ],
        _ignore_errors=True,
        _shell_executable="/bin/bash",
    )


def put_prometheus_config_file() -> None:
    files.put(
        name=f"Put file {PROM_VALUES_FILE!r}",
        src=io.StringIO(PROM_VALUES_YAML),
        dest=f"/root/{PROM_VALUES_FILE}",
    )


def install_kube_prometheus_stack_v3():
    # Install kube-prometheus-stack
    # Set namespace to "monitoring", create it if it doesn't exist.
    # Set Grafana service type to NodePort for host access.
    # defaultRules.create is true by default, no need to explicitly set it unless disabling.
    #
    #  # kubectl get clusterrolebinding karmada-apiserver-cluster-admin -o yaml

    # kubectl create clusterrolebinding karmada-apiserver-cluster-admin \
    # --clusterrole=cluster-admin --user=karmada-apiserver

    result = server.shell(
        # --version 75.18.1 \
        # --version 72.0.0 \
        # prometheus/prometheus:v3.5.0
        name="Install kube prometheus stack",
        commands=[
            """
            export KUBECONFIG="/root/.kube/karmada-apiserver.config"
            kubectl config use-context karmada-host

            helm install prometheus \
            --create-namespace -n monitoring \
            prometheus-community/kube-prometheus-stack \
            --values /root/prom-values.yaml \
            --debug

            echo "-------------------\nkubectl -n monitoring get pods:"
            kubectl -n monitoring get pods

            echo "-------------------\nkubectl -n monitoring get svc:"
            kubectl -n monitoring get svc

            echo "-------------------\nkubectl get crds | grep 'monitoring.coreos.com':"
            kubectl get crds | grep 'monitoring.coreos.com'
            """
        ],
        _shell_executable="/bin/bash",
    )
    python.call(
        name="Show installed prometheus",
        function=log_callback,
        result=result,
    )


def install_service_monitor_crds_in_api_server() -> None:
    # Base URL for the Prometheus Operator CRDs
    BASE_URL = (
        "https://raw.githubusercontent.com/prometheus-operator/"
        "prometheus-operator/v0.84.1/example/prometheus-operator-crd"
    )

    result = server.shell(
        name="Install monitor crds for karmada-apiserver",
        commands=[
            f"""
            export KUBECONFIG="/root/.kube/karmada-apiserver.config"
            kubectl config use-context karmada-apiserver

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

            kubectl create namespace monitoring || true
            """
        ],
        _shell_executable="/bin/bash",
    )
    python.call(
        name="Show installed monitor crds for karmada-apiserver",
        function=log_callback,
        result=result,
    )


main()
