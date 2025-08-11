# Experiments with Microk8s using local scripts

## The easy way (assuming you have a Hetzner server)

Run `make test-e2e` assuming:

SERVER_NAME is set to the name of the server you are running this on, e.g. `mk8s-hetzner`.
HETZNER_TOKEN is a valid Hetzner token.

You may need to tweak more values on `test-server.py`.

## The not so hard way

Set SERVER_NAME to your server address.

Push the scripts to your server using `make push-local-scripts`.

On the server, go to `/root/local-scripts` and run them one by one:

```bash
#/bin/bash

set -e

./0-prepare-server.py
./1-create-clusters-on-lxd.py
./2-setup-karmada.py
./3-check-karmada.py
./4-nginx-demo.py
./5-flask-demo-1.py
./5-flask-demo-2.py
```
