# Note: use an env variable SERVER_NAME to set the test server name.
# If not set, it defaults to "nephele".
# For instance in your .envrc (if you use direnv),
# or in your .profile / .bashrc / .zshrc / etc.
# Or you can set it in your local machine's /etc/hosts file.

SERVER_NAME?=nephele

## Deployment Makefile for Karmada on kind

deploy-demo0:
	pyinfra -y -vv --user root inventory.py \
		0-setup-server.py \
		1-clean-karmada-on-kind.py \
		1-2-deploy-karmada-on-kind.py \
		2-install-prometheus-on-kind.py
		# 3-install-prometheus-crds-on-kind.py \
		# 4-install-metrics-server-kind.py \

		# 4-2-start-grafana.py \
		# 6-2-install-basic-kind-cluster.py \

		# 8-install-smo-cli-monorepo.py \
		# 10-pull-h3ni-demo.py \
		# 11-build-hello-world.py \
		# 12-install-hello-world.py \

.PHONY: deploy-demo0
