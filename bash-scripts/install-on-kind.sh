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
    init --crds https://github.com/karmada-io/karmada/releases/download/v1.14.0/crds.tar.gz
cp /etc/karmada/karmada-apiserver.config ~/.kube/

# More checks
export KUBECONFIG="$HOME/.kube/config"
kubectl get pods -n karmada-system
kubectl config use-context host
kubectl config view

# DOESNT WORK YET!
# Check Karmada cluster (not working yet!)
kubectl --kubeconfig ~/.kube/karmada-apiserver.config \
    describe cluster
kubectl --kubeconfig ~/.kube/karmada-apiserver.config \
    describe cluster kind-karmada-cluster
