# Note: use an env variable SERVER_NAME to set the test server name.
# If not set, it defaults to "nephele".
# For instance in your .envrc (if you use direnv),
# or in your .profile / .bashrc / .zshrc / etc.
# Or you can set it in your local machine's /etc/hosts file.

SERVER_NAME?=nephele

deploy-demo3:
	pyinfra -y --user root inventory.py \
		0-setup-server.py \
		0-2-install-smo-cli-monorepo.py \
		1-clean-karmada-on-kind.py \
		1-2-deploy-karmada-on-kind.py \
		4-install-metrics-server-kind.py \
		4-2-start-grafana.py \
		5-configure-smo-cli.py \
		10-pull-h3ni-demo.py \
		15-demo-autoscaling.py


.PHONY: deploy-demo3
