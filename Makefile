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

	@make sync-code
	@make deploy

.PHONY: deploy sync-code push-code format
