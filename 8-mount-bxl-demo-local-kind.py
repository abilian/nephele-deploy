"""
Minimal recipe to mount BXL demo on kind
- brussels sample

Warning: connection as user root.

pyinfra -y -vvv --user root HOST 8-mount-bxl-demo-local-kind.py
"""

# from pyinfra import host
# from pyinfra.facts.files import File
from pyinfra.operations import apt, files, git, server
from pyinfra.operations import files, server
import io
from common import check_server
from constants import GITS, SMO_URL

KUBECONFIG = "/root/.kube/karmada-apiserver.config"
LOCAL_IP = "127.0.0.1"
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
  name: image-detection
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
        commands=[f"kind load docker-image {IMAGES[0]} -n test-cluster"],
    )


def apply_deploy_yaml() -> None:
    server.shell(
        name="Apply deploy img1 yaml",
        commands=[
            f"kubectl apply -f {IMG1_DEPLOY_FILE} --kubeconfig {KUBECONFIG}",
            f"kubectl get pods -l app=image-detection --kubeconfig {KUBECONFIG}",
        ],
    )


main()
