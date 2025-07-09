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
IMAGES = [
    "127.0.0.1:5000/image-detection",
    "127.0.0.1:5000/noise-reduction",
    "127.0.0.1:5000/custom-vo",
]
IMG1_DEPLOY_FILE = "img1-deploy.yaml"
IMG1_DEPLOY = """\
apiVersion: apps/v1
kind: Deployment
metadata:
  name: image-detection-deployment
  labels:
    app: image-detection
spec:
  replicas: 1
  selector:
    matchLabels:
      app: image-detection
  template:
    metadata:
      labels:
        app: image-detection
    spec:
      containers:
      - name: image-detection-container
        image: 127.0.0.1:5000/image-detection
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
    files.put(
        name=f"Put file {IMG1_DEPLOY_FILE!r}",
        src=io.StringIO(IMG1_DEPLOY),
        dest=f"/root/{IMG1_DEPLOY_FILE}",
    )


def kind_load_docker_image() -> None:
    IMAGES = [
        "127.0.0.1:5000/image-detection",
        "127.0.0.1:5000/noise-reduction",
        "127.0.0.1:5000/custom-vo",
    ]
    server.shell(
        name="kind load docker-image",
        commands=[f"kind load docker-image {IMAGES[0]} -n {APP_CLUSTER}"],
    )


def apply_deploy_yaml() -> None:
    server.shell(
        name="Apply deploy img1 yaml",
        commands=[
            f"kubectl apply -f {IMG1_DEPLOY_FILE} --context {APP_CONTEXT}",
        ],
    )


def check_deployed() -> None:
    server.shell(
        name="Check deployed img1",
        commands=[
            f"kubectl get pods -l app=image-detection --context {APP_CONTEXT}",
        ],
    )


def show_logs_container() -> None:
    server.shell(
        name="Show logs container img1",
        commands=[
            f"sleep 5 && kubectl logs -l app=image-detection --context {APP_CONTEXT}",
        ],
    )


main()
