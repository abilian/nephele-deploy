"""
Minimal recipe to deploy nginx using karmada as a test.

pyinfra -y -vv --user root ${SERVER_NAME}  13-deploy-nginx.py
"""

import io
from textwrap import dedent

from pyinfra.operations import files, python, server

from common import log_callback

LOAD_K_CONFIG_CMD = (
    "export KUBECONFIG=/root/.kube/karmada.config:/root/.kube/members.config"
)
MANIFEST_FILE = "nginx_manifest.yml"
MANIFEST_YML = """\
apiVersion: apps/v1
kind: Deployment
metadata:
  name: nginx
  namespace: demo
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
        image: nginx:1.25-alpine
        ports:
        - containerPort: 80
"""

PROPAGATION_1_FILE = "propagation1.yaml"
PROPAGATION_1_YAML = """\
apiVersion: policy.karmada.io/v1alpha1
kind: PropagationPolicy
metadata:
  name: nginx-pp
  namespace: demo
spec:
  resourceSelectors:
    - apiVersion: apps/v1
      kind: Deployment
      name: nginx
  placement:
    clusterAffinity:
      clusterNames:
        - member1
    replicaScheduling:
      replicaDivisionPreference: Weighted
      weightPreference:
        staticWeightList:
          - targetCluster:
              clusterNames:
                - member1
            weight: 1
"""

EXPOSE1_FILE = "expose1.yaml"
EXPOSE1_YAML = """\
apiVersion: v1
kind: Service
metadata:
  name: nginx-service
  namespace: demo
spec:
  selector:
    app: nginx
  ports:
    - protocol: TCP
      port: 80
      targetPort: 80
"""


def main() -> None:
    install_nginx_member(1)


def member_context_cmd(mid: int) -> str:
    return f"""
            {LOAD_K_CONFIG_CMD}
            kubectl config use-context member{mid}
            """


def host_context_cmd() -> str:
    return f"""
            {LOAD_K_CONFIG_CMD}
            kubectl config use-context karmada-host
            """


def install_nginx_member(mid: int):
    context = """
    export KUBECONFIG=/root/.kube/karmada.config:/root/.kube/members.config
    kubectl config use-context karmada-apiserver
    """
    context_member1 = """
    export KUBECONFIG=/root/.kube/karmada.config:/root/.kube/members.config
    kubectl config use-context member1
    """

    result = server.shell(
        name="Check status of clusters",
        commands=[
            dedent(f"""\
            {context}
            kubectl get clusters
            """)
        ],
        _shell_executable="/bin/bash",
    )
    python.call(
        name="Show status of clusters, expected push mode",
        function=log_callback,
        result=result,
    )

    server.shell(
        name="Create namespace demo",
        commands=[
            dedent(f"""\
            {context}
            if kubectl get namespaces | grep -q demo; then
              echo "Namespace 'demo' already exists."
            else
              echo "Namespace 'demo' does not exist. Creating it now..."
              kubectl create namespace demo
            fi
            """)
        ],
        _shell_executable="/bin/bash",
    )

    result = server.shell(
        name="Check contexts",
        commands=[
            dedent(f"""\
            {context}
            kubectl config get-contexts
            """)
        ],
        _shell_executable="/bin/bash",
    )
    python.call(
        name="Show contexts",
        function=log_callback,
        result=result,
    )

    files.put(
        name=f"Put nginx manifest file {MANIFEST_FILE}",
        src=io.StringIO(MANIFEST_YML),
        dest=f"/root/{MANIFEST_FILE}",
    )

    result = server.shell(
        name=f"kubectl apply {MANIFEST_FILE}",
        commands=[
            dedent(f"""\
            {context}
            kubectl apply -f /root/{MANIFEST_FILE}
            """)
        ],
        _shell_executable="/bin/bash",
    )
    python.call(
        name=f"Show apply {MANIFEST_FILE}",
        function=log_callback,
        result=result,
    )

    files.put(
        name=f"Put cluster propagation rule {PROPAGATION_1_FILE}",
        src=io.StringIO(PROPAGATION_1_YAML),
        dest=f"/root/{PROPAGATION_1_FILE}",
    )

    result = server.shell(
        name=f"kubectl apply {PROPAGATION_1_FILE}",
        commands=[
            dedent(f"""\
            {context}
            kubectl apply -f /root/{PROPAGATION_1_FILE}
            """)
        ],
        _shell_executable="/bin/bash",
    )
    python.call(
        name=f"Show apply {MANIFEST_FILE}",
        function=log_callback,
        result=result,
    )

    result = server.shell(
        name="Check deployed",
        commands=[
            dedent(f"""\
            {context}
            kubectl karmada get deploy -n demo
            """)
        ],
        _shell_executable="/bin/bash",
    )
    python.call(
        name="Show deployed",
        function=log_callback,
        result=result,
    )

    result = server.shell(
        name="Verify deployed in member1",
        commands=[
            dedent(f"""\
            {context_member1}
            kubectl -n demo get deploy nginx
            """)
        ],
        _shell_executable="/bin/bash",
    )
    python.call(
        name="Show deployed in member1",
        function=log_callback,
        result=result,
    )

    files.put(
        name=f"Put Expostion file {EXPOSE1_FILE}",
        src=io.StringIO(EXPOSE1_YAML),
        dest=f"/root/{EXPOSE1_FILE}",
    )

    result = server.shell(
        name=f"kubectl apply {EXPOSE1_FILE}",
        commands=[
            dedent(f"""\
            {context_member1}
            kubectl apply -f /root/{EXPOSE1_FILE}
            """)
        ],
        _shell_executable="/bin/bash",
    )
    python.call(
        name=f"Show apply {EXPOSE1_FILE}",
        function=log_callback,
        result=result,
    )

    result = server.shell(
        name="Verify service nginx",
        commands=[
            dedent(f"""\
            {context_member1}
            kubectl -n demo get svc nginx-service
            """)
        ],
        _shell_executable="/bin/bash",
    )
    python.call(
        name="Show service nginx",
        function=log_callback,
        result=result,
    )

    server.shell(
        name="Port-Forward service nginx",
        commands=[
            dedent(f"""\
            {context_member1}
            kubectl -n demo port-forward svc/nginx-service 8080:80 &
            sleep 5
            curl http://localhost:8080 | head -5
            """)
        ],
        _shell_executable="/bin/bash",
        _get_pty=True,
    )
    python.call(
        name="Show service nginx with curl",
        function=log_callback,
        result=result,
    )


main()
