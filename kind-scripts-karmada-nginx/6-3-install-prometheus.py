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

pyinfra -y -vv --user root ${SERVER_NAME} 6-3-install-prometheus.py
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

# Define the Prometheus Operator version
VERSION = "v0.78.2"
# Base URL for the Prometheus Operator CRDs
BASE_URL = (
    "https://raw.githubusercontent.com/prometheus-operator/"
    f"prometheus-operator/{VERSION}/example/prometheus-operator-crd"
)

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
"""


# f"""\
# prometheus:
#   prometheusSpec:
#     enableRemoteWriteReceiver: true
#     scrapeInterval: 30s
#     evaluationInterval: 30s
#     externalLabels:
#       cluster: {CLUSTER_NAME}
#   service:
#     nodePort: 30090
#     type: NodePort
# grafana:
#   service:
#     nodePort: 30080
#     type: NodePort
# defaultRules:
#   create: false
#   test-rules:
#       groups:
#       - name: smo-alerts
#         rules: []
# alertmanager:
#   service:
#     nodePort: 30093
#     type: NodePort
#   config:
#     global:
#       resolve_timeout: 5m
#     receivers:
#       - name: 'webhook-receiver'
#         webhook_configs:
#           # Note: Replace 127.0.0.1 with the actual IP address of your SMO service
#           - url: '{SMO_URL}'
#             send_resolved: false
#     route:
#       group_by: ['job']
#       group_wait: 10s
#       group_interval: 1m
#       receiver: 'webhook-receiver'
#       repeat_interval: 1m
#       routes:
#         - receiver: "webhook-receiver"
# """

# PROM_CLUSTER_NAME = "prom-cluster"
# PROM_CONFIG_FILE = "prom-kins-config.yaml"
# PROM_CONFIG = f"""\
#  kind: Cluster
#  apiVersion: kind.x-k8s.io/v1alpha4
#  name: {PROM_CLUSTER_NAME}
#  networking:
#    apiServerAddress: "0.0.0.0" # Bind to all interfaces inside the container
#    apiServerPort: 6444 # aka 6443 + 1
# """
# PROM_KUBECONF_PATH = f"/root/.kube/{PROM_CLUSTER_NAME}.kubeconfig"


def main() -> None:
    add_prometheus_repo()
    remove_prior_prometheus_cluster()
    put_prometheus_config_file()
    install_kube_prometheus_stack_v2()
    # install_crds_in_control_pane()


def add_prometheus_repo() -> None:
    REPO = "https://prometheus-community.github.io/helm-charts"
    server.shell(
        name="Add helm repo for prometheus",
        commands=[
            f"helm repo add prometheus-community {REPO}",
            "helm repo update",
        ],
    )


def remove_prior_prometheus_cluster() -> None:
    server.shell(
        name="Uninstall service prometheus monitoring",
        commands=[
            """
            export KUBECONFIG="/root/.kube/karmada.config"
            kubectl config use-context karmada-host
            helm uninstall prometheus -n monitoring
            """
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


def install_kube_prometheus_stack_v2():
    # Install kube-prometheus-stack
    # Set namespace to "monitoring", create it if it doesn't exist.
    # Set Grafana service type to NodePort for host access.
    # defaultRules.create is true by default, no need to explicitly set it unless disabling.
    server.shell(
        name="Install kube prometheus stack",
        commands=[
            f"""
            export KUBECONFIG="/root/.kube/karmada.config"
            kubectl config use-context karmada-host

            helm install prometheus --create-namespace -n monitoring \
            prometheus-community/kube-prometheus-stack --values /root/{PROM_VALUES_FILE}
            """
        ],
        _shell_executable="/bin/bash",
    )


# def install_kube_prometheus_stack():
#     # Install kube-prometheus-stack
#     # Set namespace to "monitoring", create it if it doesn't exist.
#     # Set Grafana service type to NodePort for host access.
#     # defaultRules.create is true by default, no need to explicitly set it unless disabling.
#     server.shell(
#         name="Install kube prometheus stack",
#         commands=[
#             (
#                 "helm install prometheus prometheus-community/kube-prometheus-stack "
#                 "--namespace monitoring --create-namespace "
#                 "--set grafana.service.type=NodePort "
#                 "--set prometheus.prometheusSpec.serviceMonitorSelectorNilUsesHelmValues=false "
#                 "--set prometheus.prometheusSpec.podMonitorSelectorNilUsesHelmValues=false"
#             ),
#         ],
#     )


# def install_crds_in_control_pane():
#     base = f"kubectl apply --server-side -f {BASE_URL}"
#     server.shell(
#         name="Install crds in control pane",
#         commands=[
#             f"{base}/monitoring.coreos.com_alertmanagerconfigs.yaml --kubeconfig {KUBECONFIG}",
#             f"{base}/monitoring.coreos.com_alertmanagers.yaml --kubeconfig {KUBECONFIG}",
#             f"{base}/monitoring.coreos.com_podmonitors.yaml --kubeconfig {KUBECONFIG}",
#             f"{base}/monitoring.coreos.com_probes.yaml --kubeconfig {KUBECONFIG}",
#             f"{base}/monitoring.coreos.com_prometheusagents.yaml --kubeconfig {KUBECONFIG}",
#             f"{base}/monitoring.coreos.com_prometheuses.yaml --kubeconfig {KUBECONFIG}",
#             f"{base}/monitoring.coreos.com_prometheusrules.yaml --kubeconfig {KUBECONFIG}",
#             f"{base}/monitoring.coreos.com_scrapeconfigs.yaml --kubeconfig {KUBECONFIG}",
#             f"{base}/monitoring.coreos.com_servicemonitors.yaml --kubeconfig {KUBECONFIG}",
#             f"{base}/monitoring.coreos.com_thanosrulers.yaml --kubeconfig {KUBECONFIG}",
#         ],
#     )
#     server.shell(
#         name="Create the monitoring namespace",
#         commands=[f"kubectl create ns monitoring --kubeconfig {KUBECONFIG}"],
#     )


# def __install_prometheus_cluster() -> None:
#     files.put(
#         name=f"Put file {PROM_CONFIG_FILE!r}",
#         src=io.StringIO(PROM_CONFIG),
#         dest=f"/root/{PROM_CONFIG_FILE}",
#     )
#     server.shell(
#         name=f"Create kind cluster with name {PROM_CLUSTER_NAME!r}",
#         commands=f"kind create cluster -n {PROM_CLUSTER_NAME} --config /root/{PROM_CONFIG_FILE}",
#         _get_pty=True,
#     )

#     server.shell(
#         name=f"Export confif {PROM_KUBECONF_PATH!r}",
#         commands=(
#             f"kind get kubeconfig --name {PROM_CLUSTER_NAME}  > {PROM_KUBECONF_PATH}"
#         ),
#         _get_pty=True,
#     )

#     server.shell(
#         name=f"Join cluster {PROM_CLUSTER_NAME} to Karmada.",
#         commands=(
#             "kubectl karmada --kubeconfig /root/.kube/config "
#             f"join {PROM_CLUSTER_NAME} "
#             f"--cluster-kubeconfig={PROM_KUBECONF_PATH} "
#             f'--cluster-context="kind-{PROM_CLUSTER_NAME}" '
#         ),
#         _get_pty=True,
#     )

#     server.shell(
#         name=f"Waiting cluster {PROM_CLUSTER_NAME} ready",
#         commands=(
#             "kubectl -kubeconfig ~/.kube/config "
#             "wait --for=condition=Ready "
#             f'"cluster.cluster.karmada.io/{PROM_CLUSTER_NAME}" '
#             "--timeout=5m"
#         ),
#         _get_pty=True,
#     )

#     server.shell(
#         name="Install prometheus as monitoring",
#         commands=(
#             f"helm install prometheus --create-namespace -n monitoring "
#             f"prometheus-community/kube-prometheus-stack --values {PROM_VALUES_FILE}"
#         ),
#     )
#     result = server.shell(
#         name="Show pods of monitoring",
#         commands=[
#             "kubectl get pods -n monitoring",
#         ],
#     )
#     python.call(
#         name="Show pods of monitoring",
#         function=log_callback,
#         result=result,
#     )
#     result = server.shell(
#         name="Get joined of monitoring",
#         commands=[
#             "kubectl karmada --kubeconfig /root/.kube/config get clusters",
#         ],
#     )
#     python.call(
#         name="Show joined of monitoring",
#         function=log_callback,
#         result=result,
#     )


main()
