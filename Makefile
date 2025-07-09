# Note: use an env variable SERVER_IP to set the server IP address
# For instance in your .envrc (if you use direnv)
# Or in your .profile / .bashrc / .zshrc / etc.

SERVER_IP?=localhost

deploy:
	pyinfra -y --user root inventory.py 0-setup-server.py
	pyinfra -y --user root inventory.py 1-build-bxl-demo.py
	pyinfra -y --user root inventory.py 2-deploy-karmada-on-mk8s.py
	pyinfra -y --user root inventory.py 3-more.py

deploy-kind-jd:
	cd kind_scripts ; pyinfra -y --user root inventory-jd.py \
	0-setup-server.py \
	1-deploy-karmada-on-kind.py \
	2-install-prometheus-on-kind.py \
	3-install-prometheus-crds-on-kind.py \
	4-install-metrics-server-kind.py \
	6-install-some-kind-cluster.py \
	7-build-bxl-demo-local-kind.py

sync-code:
	git pull eclipse main
	git pull origin main
	@make push-code


push-code:
	git push eclipse main
	git push origin main


format:
	isort .
	ruff format .

sync-with-server:
	watchfiles "rsync -e ssh -avz bash-scripts/ root@${SERVER_IP}:/root/scripts/" bash-scripts/

.PHONY: deploy sync-code push-code format deploy-kind-jd
