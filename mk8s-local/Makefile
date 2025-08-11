test-e2e:
	./test-server.py

## Temp hack
push-local-scripts:
	watchfiles "rsync -e ssh -avz --delete ./local-scripts/ root@${SERVER_NAME}:/root/local-scripts/" .
