#!/usr/bin/env bash

set -euo pipefail


# Check
kubectl cluster-info --kubeconfig ~/.kube/config

# Create a cluster, let's call it "karmada-cluster"
kind create cluster -n karmada-cluster

# Check
kubectl --kubeconfig ~/.kube/karmada-apiserver.config describe cluster karmada-cluster

# Install karmada
curl -s https://raw.githubusercontent.com/karmada-io/karmada/master/hack/install-cli.sh | sudo bash -s kubectl-karmada

# Init Karmada
kubectl karmada init --crds https://github.com/karmada-io/karmada/releases/download/v1.2.0/crds.tar.gz --kubeconfig=$HOME/.kube/config
cp /etc/karmada/karmada-apiserver.config ~/.kube/

# Check Karmada
kubectl get pods -n karmada-system --kubeconfig ~/.kube/config
