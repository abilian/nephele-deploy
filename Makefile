# Note: use an env variable SERVER_NAME to set the test server name.
# If not set, it defaults to "nephele".
# For instance in your .envrc (if you use direnv),
# or in your .profile / .bashrc / .zshrc / etc.
# Or you can set it in your local machine's /etc/hosts file.

SERVER_NAME?=nephele

## Deployment Makefile for Karmada on kind

deploy-kind:
	cd kind-scripts ; pyinfra -y --user root inventory.py \
		0-setup-server.py \
		1-deploy-karmada-on-kind.py \
		2-install-prometheus-on-kind.py \
		3-install-prometheus-crds-on-kind.py \
		4-install-metrics-server-kind.py \
		6-install-some-kind-cluster.py \
		7-build-bxl-demo-local-kind.py

deploy-demo0:
	$(MAKE) -C kind-scripts-demo0

## Deployment Makefile for Karmada on microk8s (not fully working)
deploy:
	pyinfra -y --user root inventory.py 0-setup-server.py
	pyinfra -y --user root inventory.py 1-build-bxl-demo.py
	pyinfra -y --user root inventory.py 2-deploy-karmada-on-mk8s.py
	pyinfra -y --user root inventory.py 3-more.py

## Make a movie
make-movie:
	asciinema rec -c "make deploy-kind" -e SERVER_NAME


## Synchronize code with the remote repositories
sync-code:
	git pull eclipse main
	git pull origin main
	@make push-code


## Push code to the remote repositories
push-code:
	git push eclipse main
	git push origin main


## Format python code
format:
	isort .
	ruff format .


## Synchronize bash scripts with the server for remote execution
sync-with-server:
	watchfiles "rsync -e ssh -avz bash-scripts/ root@${SERVER_NAME}:/root/scripts/" bash-scripts/


.PHONY: deploy sync-code push-code format deploy-kind
