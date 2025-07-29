# Note: use an env variable SERVER_NAME to set the test server name.
# If not set, it defaults to "nephele".
# For instance in your .envrc (if you use direnv),
# or in your .profile / .bashrc / .zshrc / etc.
# Or you can set it in your local machine's /etc/hosts file.

SERVER_NAME?=nephele

deploy-test2:
	pyinfra -y --user root inventory.py \
		0-setup-server.py \
		2-install-kind-kubectl.py \
		4-install-kubectl-karmada.py \
		5-install-nephele-smo.py \
		6-3-install-prometheus.py \
		5-install-prometheus-members.py \
		13-deploy-nginx.py

.PHONY: deploy-test2
