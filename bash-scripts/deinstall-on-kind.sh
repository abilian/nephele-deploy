#!/usr/bin/env bash

set -euo pipefail

kubectl karmada deinit
kind delete cluster -n karmada-cluster
