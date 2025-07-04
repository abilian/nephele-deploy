# Note: use an env variable SERVER_IP to set the server IP address
# For instance in your .envrc (if you use direnv)
# Or in your .profile / .bashrc / .zshrc / etc.

SERVER_IP?=localhost

deploy:
	pyinfra -y --user root inventory.py 0-setup-server.py
	pyinfra -y --user root inventory.py 1-build-bxl-demo.py
	pyinfra -y --user root inventory.py 2-deploy-karmada-on-mk8s.py
	pyinfra -y --user root inventory.py 3-more.py

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

.PHONY: deploy sync-code push-code format
