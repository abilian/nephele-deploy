"""
Minimal recipe to mount BXL demo on kind
- brussels sample

Warning: connection as user root.

pyinfra -y -vvv --user root HOST 8-mount-bxl-demo-local-kind.py
"""

import io

# from pyinfra import host
# from pyinfra.facts.files import File
from pyinfra.operations import files, server

from common import check_server

KUBECONFIG = "/root/.kube/karmada-apiserver.config"
LOCAL_IP = "127.0.0.1"
APP_CLUSTER = "bxl-cluster"
APP_CONTEXT = "kind-bxl-cluster"

APP_NAMES = ["image-detection", "noise-reduction", "custom-vo"]
IMAGES = [
    "127.0.0.1:5000/image-detection",
    "127.0.0.1:5000/noise-reduction",
    "127.0.0.1:5000/custom-vo",
]
# IMG1_DEPLOY_FILE = "image-detection-deploy.yaml"
# IMG2_DEPLOY_FILE = "noise-reduction-deploy.yaml"
# IMG3_DEPLOY_FILE = "custom-vo-deploy.yaml"

DEPLOY_TEMPLATE = """\
apiVersion: apps/v1
kind: Deployment
metadata:
  name: __name__-deployment
  labels:
    app: __name__
spec:
  replicas: 1
  selector:
    matchLabels:
      app: __name__
  template:
    metadata:
      labels:
        app: __name__
    spec:
      containers:
      - name: __name__-container
        image: 127.0.0.1:5000/__name__
        imagePullPolicy: Never
        ports:
        - containerPort: 8080
"""


def main() -> None:
    check_server()
    put_deploy1_config_file()
    kind_load_docker_image()
    apply_deploy_yaml()
    check_deployed()
    show_logs_container()


def put_deploy1_config_file() -> None:
    for name in APP_NAMES:
        deploy_yaml = DEPLOY_TEMPLATE.replace("__name__", name)
        filename = f"{name}-deploy.yaml"
        files.put(
            name=f"Put file {filename!r}",
            src=io.StringIO(deploy_yaml),
            dest=f"/root/{filename}",
        )


def kind_load_docker_image() -> None:
    for name in APP_NAMES:
        image_name = f"127.0.0.1:5000/{name}"
        server.shell(
            name=f"kind load docker-image {image_name}",
            commands=[f"kind load docker-image {image_name} -n {APP_CLUSTER}"],
        )


def apply_deploy_yaml() -> None:
    for name in APP_NAMES:
        filename = f"{name}-deploy.yaml"
        server.shell(
            name=f"Apply deploy {filename}",
            commands=[
                f"kubectl apply -f {filename} --context {APP_CONTEXT}",
            ],
        )


def check_deployed() -> None:
    for name in APP_NAMES:
        server.shell(
            name=f"Check deployed {name!r}",
            commands=[
                f"kubectl get pods -l app={name} --context {APP_CONTEXT}",
            ],
        )


def show_logs_container() -> None:
    for name in APP_NAMES:
        server.shell(
            name=f"Show logs container {name!r}",
            commands=[
                f"sleep 5 && kubectl logs -l app={name} --context {APP_CONTEXT}",
            ],
        )


main()
