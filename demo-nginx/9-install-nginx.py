"""
Minimal recipe to deploy Metrics Server on kind on ubuntu server.

pyinfra -y -vv --user root ${SERVER_NAME} 9-install-nginx.py
"""

import io

from pyinfra.operations import files, python, server

from common import log_callback

KUBECONFIG = "/root/.kube/config"


def main() -> None:
    deploy_nginx_demo()
    check_nginx_status()


def install_metrics_server() -> None:
    COMPONENT_SOURCE = (
        "https://github.com/kubernetes-sigs/metrics-server/"
        "releases/latest/download/components.yaml"
    )
    server.shell(
        name="Install Metrics Server",
        commands=[
            f"wget {COMPONENT_SOURCE}",
            "sed -i '/- args:/a \        - --kubelet-insecure-tls' components.yaml",
            f"kubectl apply -f components.yaml --kubeconfig {KUBECONFIG}",
            f"kubectl get crds --kubeconfig {KUBECONFIG}",
        ],
    )


def deploy_nginx_demo():
    nginx_manifest = """
apiVersion: apps/v1
kind: Deployment
metadata:
  name: nginx-deployment
  labels:
    app: nginx
spec:
  replicas: 2
  selector:
    matchLabels:
      app: nginx
  template:
    metadata:
      labels:
        app: nginx
    spec:
      containers:
      - name: nginx
        image: nginx:latest
        ports:
        - containerPort: 80
---
apiVersion: v1
kind: Service
metadata:
  name: nginx-service
spec:
  selector:
    app: nginx
  ports:
    - protocol: TCP
      port: 80
      targetPort: 80
  type: NodePort
"""
    manifest_file = "/root/nginx-demo.yaml"

    files.put(
        name="Put nginx deployment manifest",
        src=io.StringIO(nginx_manifest),
        dest=manifest_file,
    )

    server.shell(
        name="Deploy nginx",
        commands=[f"kubectl --kubeconfig={KUBECONFIG} apply -f {manifest_file}"],
    )


def check_nginx_status():
    """Checks if the Nginx deployment pods are running."""
    LOG = "/root/log_niginx.txt"
    RETRY = 10
    WAIT = 5
    server.shell(
        name="Wait pods",
        commands=[
            f"""
                echo "" > {LOG}
                count=0
                until grep -q 'Running' {LOG} || [ "$count" -ge "{RETRY}" ]
                do
                    sleep {WAIT}
                    kubectl --kubeconfig={KUBECONFIG} get pods -l app=nginx \
                    2>&1 | tee {LOG}
                    count=$((count + 1))
                    echo "-- try loop number: $count"
                    done
                """,
            f"grep -q 'Running' {LOG}",
        ],
        _get_pty=True,
    )

    result = server.shell(
        name="Check nginx service port",
        commands=[f"kubectl --kubeconfig={KUBECONFIG} get svc nginx-service"],
    )
    python.call(
        name="Show nginx service port",
        function=log_callback,
        result=result,
    )

    result = server.shell(
        name="Find all kubernetes pods",
        commands=["kubectl get pods -A"],
        _get_pty=True,
    )
    python.call(
        name="Show all kubernetes pods",
        function=log_callback,
        result=result,
    )

    result = server.shell(
        name="Find docker IP for nginx",
        commands=[
            """
            port=$(kubectl get svc nginx-service | grep -oP '^.*80:\\K\\d+' | head -n 1)
            ref=$(docker ps -q -f name=host-control-plane)
            ip=$(docker inspect -f '{{.NetworkSettings.Networks.kind.IPAddress}}' ${ref})
            echo "use the port on this IP: ${ip}:${port}"
            curl http://${ip}:${port} | head -5
            """
        ],
        _get_pty=True,
    )
    python.call(
        name="Show nginx docker IP",
        function=log_callback,
        result=result,
    )


main()
