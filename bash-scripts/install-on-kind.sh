#!/usr/bin/env bash

set -veuo pipefail

# Create a cluster, let's call it "karmada-cluster"
kind create cluster -n karmada-cluster

# Check
kubectl cluster-info --kubeconfig ~/.kube/config

# Install karmada
curl -s https://raw.githubusercontent.com/karmada-io/karmada/master/hack/install-cli.sh | sudo bash -s kubectl-karmada

# Init Karmada
kubectl karmada  --kubeconfig ~/.kube/config \
    init --crds https://github.com/karmada-io/karmada/releases/download/v1.2.0/crds.tar.gz
cp /etc/karmada/karmada-apiserver.config ~/.kube/

# Check Karmada
kubectl --kubeconfig ~/.kube/config \
    get pods -n karmada-system
kubectl --kubeconfig ~/.kube/karmada-apiserver.config \
    describe cluster karmada-cluster
