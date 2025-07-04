#!/usr/bin/env bash

set -v

kubectl karmada deinit
kind delete cluster -n karmada-cluster
