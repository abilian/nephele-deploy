deploy-mk8s-demo0:
	pyinfra -y --user root \
		_common/inventory.py \
		_common/0-setup-server.py \
		_common/2-install-microk8s.py \
		_common/4-install-karmada-on-microk8s.py \
		_common/10-install-nephele-smo.py \
		demo0-hello-world/11-pull-h3ni-demo.py \
		demo0-hello-world/12-deploy-demo-hello-world.py

deploy-mk8s-demo1:
	pyinfra -y --user root \
		_common/inventory.py \
		_common/0-setup-server.py \
		_common/2-install-microk8s.py \
		_common/4-install-karmada-on-microk8s.py \
		_common/10-install-nephele-smo.py \
		demo1-nginx/13-deploy-nginx.py

deploy-mk8s-demo2:
	pyinfra -y --user root \
		_common/inventory.py \
		_common/0-setup-server.py \
		_common/2-install-microk8s.py \
		_common/4-install-karmada-on-microk8s.py \
		_common/10-install-nephele-smo.py \
		demo2-bxl/12-install-bxl-demo.py

.PHONY: deploy-mk8s-demo0 deploy-mk8s-demo1 deploy-mk8s-demo2
