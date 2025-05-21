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
