#!/bin/sh

set -e

pyinfra -y --user root inventory.py setup-server.py
pyinfra -y --user root inventory.py run-bxl-demo.py
