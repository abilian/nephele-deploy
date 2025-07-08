#!/usr/bin/env bash

set -veuo pipefail

helm install prometheus --create-namespace -n monitoring \
   prometheus-community/kube-prometheus-stack --values prom-values.yaml

# Check if the Prometheus pods are running
kubectl get pods -n monitoring
