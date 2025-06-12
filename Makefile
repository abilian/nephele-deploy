deploy:
	pyinfra -y --user root inventory.py setup-server.py
	pyinfra -y --user root inventory.py run-bxl-demo.py
	pyinfra -y --user root inventory.py

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


.PHONY: deploy sync-code push-code format
