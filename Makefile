# Note: use an env variable SERVER_NAME to set the test server name.
# If not set, it defaults to "nephele".
# For instance in your .envrc (if you use direnv),
# or in your .profile / .bashrc / .zshrc / etc.
# Or you can set it in your local machine's /etc/hosts file.

SERVER_NAME?=nephele

## Deployment Makefile for Karmada on kind


deploy-demo0-nephele:
	$(MAKE) -C kind-scripts-demo-0-hello-world

deploy-demo0-smo-cli:
	$(MAKE) -C kind-scripts-demo-0-hello-world-smo-mono

deploy-demo2:
	$(MAKE) -C kind-scripts-demo-2-gpu-offloading

deploy-bxl:
	$(MAKE) -C kind-scripts-demo-bxl

deploy-nginx:
	$(MAKE) -C kind-scripts-demo-nginx


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


.PHONY: sync-code push-code format deploy-demo0-nephele deploy-demo0-smo-cli deploy-demo2 deploy-bxl deploy-nginx
