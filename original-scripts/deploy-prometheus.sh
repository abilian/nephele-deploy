#!/usr/bin/env bash

set -euo pipefail

# Define the Prometheus Operator version
VERSION="v0.78.2"

# Base URL for the Prometheus Operator CRDs
BASE_URL="https://raw.githubusercontent.com/prometheus-operator/prometheus-operator/$VERSION/example/prometheus-operator-crd"

# Kubeconfig file of the Karmada control plane
KUBECONFIG="$HOME/.kube/karmada-apiserver.config"

# Apply each CRD with server-side apply
kubectl apply --server-side -f $BASE_URL/monitoring.coreos.com_alertmanagerconfigs.yaml --kubeconfig $KUBECONFIG
kubectl apply --server-side -f $BASE_URL/monitoring.coreos.com_alertmanagers.yaml --kubeconfig $KUBECONFIG
kubectl apply --server-side -f $BASE_URL/monitoring.coreos.com_podmonitors.yaml --kubeconfig $KUBECONFIG
kubectl apply --server-side -f $BASE_URL/monitoring.coreos.com_probes.yaml --kubeconfig $KUBECONFIG
kubectl apply --server-side -f $BASE_URL/monitoring.coreos.com_prometheusagents.yaml --kubeconfig $KUBECONFIG
kubectl apply --server-side -f $BASE_URL/monitoring.coreos.com_prometheuses.yaml --kubeconfig $KUBECONFIG
kubectl apply --server-side -f $BASE_URL/monitoring.coreos.com_prometheusrules.yaml --kubeconfig $KUBECONFIG
kubectl apply --server-side -f $BASE_URL/monitoring.coreos.com_scrapeconfigs.yaml --kubeconfig $KUBECONFIG
kubectl apply --server-side -f $BASE_URL/monitoring.coreos.com_servicemonitors.yaml --kubeconfig $KUBECONFIG
kubectl apply --server-side -f $BASE_URL/monitoring.coreos.com_thanosrulers.yaml --kubeconfig $KUBECONFIG

# Create the monitoring namespace
kubectl create ns monitoring --kubeconfig $KUBECONFIG
