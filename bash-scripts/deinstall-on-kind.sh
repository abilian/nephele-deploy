#!/usr/bin/env bash

set -v

yes | kubectl karmada deinit
yes | kind delete cluster -n karmada-cluster
