# SERVER_NAME?=nephele

deploy-demo0:
	pyinfra -y --user root \
		_common/inventory.py \
		_common/0-setup-server.py \
		_common/2-install-kind-kubectl.py \
		_common/4-install-kubectl-karmada.py \
		_common/8-merge-kube-configs.py \
		_common/5-install-prometheus.py \
		_common/6-install-prometheus-members.py \
		_common/10-install-nephele-smo.py \
		demo0-hello-world/11-pull-h3ni-demo.py \
		demo0-hello-world/12-deploy-demo-hello-world.py

# Was:
# 	pyinfra -y --user root inventory.py \
# 		0-setup-server.py \
# 		2-install-kind-kubectl.py \
# 		4-install-kubectl-karmada.py \
# 		8-merge-kube-configs.py \
# 		5-install-prometheus.py \
# 		6-install-prometheus-members.py \
# 		10-install-nephele-smo.py \
# 		11-pull-h3ni-demo.py \
# 		12-deploy-demo-hello-world.py

deploy-demo1:
	pyinfra -y --user root \
		_common/inventory.py \
		_common/0-setup-server.py \
		_common/2-install-kind-kubectl.py \
		_common/4-install-kubectl-karmada.py \
		_common/8-merge-kube-configs.py \
		_common/5-install-prometheus.py \
		_common/6-install-prometheus-members.py \
		_common/10-install-nephele-smo.py \
		demo1-nginx/13-deploy-nginx.py

# Was:
# 	pyinfra -y --user root inventory.py \
# 		0-setup-server.py \
# 		2-install-kind-kubectl.py \
# 		4-install-kubectl-karmada.py \
# 		8-merge-kube-configs.py \
# 		5-install-prometheus.py \
# 		6-install-prometheus-members.py \
# 		10-install-nephele-smo.py \
# 		13-deploy-nginx.py

deploy-demo2:
	pyinfra -y --user root \
		_common/inventory.py \
		_common/0-setup-server.py \
		_common/2-install-kind-kubectl.py \
		_common/4-install-kubectl-karmada.py \
		_common/8-merge-kube-configs.py \
		_common/5-install-prometheus.py \
		_common/6-install-prometheus-members.py \
		_common/10-install-nephele-smo.py \
		demo2-bxl/12-install-bxl-demo.py

# Was:
# 	pyinfra -y --user root inventory.py \
# 		0-setup-server.py \
# 		2-install-kind-kubectl.py \
# 		4-install-kubectl-karmada.py \
# 		8-merge-kube-configs.py \
# 		5-install-prometheus.py \
# 		6-install-prometheus-members.py \
# 		10-install-nephele-smo.py \
# 		12-install-bxl-demo.py

.PHONY: deploy-demo0 deploy-demo1 deploy-demo2
