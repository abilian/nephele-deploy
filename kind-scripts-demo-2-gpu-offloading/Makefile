# Note: use an env variable SERVER_NAME to set the test server name.
# If not set, it defaults to "nephele".
# For instance in your .envrc (if you use direnv),
# or in your .profile / .bashrc / .zshrc / etc.
# Or you can set it in your local machine's /etc/hosts file.

SERVER_NAME?=nephele

deploy-demo2:
	pyinfra -y --user root inventory.py \
		0-setup-server.py \
		2-install-kind-kubectl.py \
		3-install-kubectl-karmada.py \
		4-merge-kube-configs.py \
		5-install-prometheus.py \
		6-install-prometheus-members.py \
		10-install-nephele-smo.py \
		11-pull-h3ni-demo.py \
		14-deploy-demo-2.py


.PHONY: deploy-demo2
