"""
Minimal recipe build for the hello-world app.

Warning: connection as user root.

pyinfra -y -v --user root ${SERVER_NAME} 12-deploy-smo-demo-hello-world.py
"""

from pyinfra import host
from pyinfra.facts.hardware import Ipv4Addrs
from pyinfra.operations import python, server

from common import log_callback
from constants import GITS

TOP_DIR = f"{GITS}/h3ni-demos/"
SMO_URL = "http://127.0.0.1:8000"
REGISTRY_URL = "http://host.docker.internal:5000"
DEMO = f"{GITS}/h3ni-demos/0-hello-world-demo"
PROJECT = "demo0"
GRAPH_NAME = "hello-world-graph"
SMO_MONO = "smo-monorepo"
REPO = f"{GITS}/{SMO_MONO}"
SMO_CLI = "/usr/local/bin/smo-cli"
INTERNAL_IP = "host.docker.internal"


def main() -> None:
    clean_installed_graphs()
    prepare_hello_world()
    deploy_on_smo()
    smo_show_graph_list()
    # check_clusters()
    find_kubernetes_pods()
    find_demo0()


def clean_installed_graphs() -> None:
    for name in (GRAPH_NAME, "image-detection-graph"):
        server.shell(
            name=f"Remove prior known graph {name}",
            # commands=[(f"yes | {SMO_CLI} graph remove {name} || true")],
            commands=[
                f"""
                cd {REPO}
                . .venv/bin/activate

                export KUBECONFIG="/root/.kube/karmada-apiserver.config"
                kubectl config use-context karmada-apiserver

                yes | {SMO_CLI} graph remove {name} || true
                """
            ],
            _get_pty=True,
            _shell_executable="/bin/bash",
        )


def prepare_hello_world() -> None:
    ips = host.get_fact(Ipv4Addrs)
    eth0 = ips["eth0"][0]
    server.shell(
        name="Adapt image name and address",
        commands=[
            f"""
            cd {DEMO}/hdag

            # keep localhost, deploying from outside cluster
            # perl -pi -e 's/127.0.0.1/{INTERNAL_IP}/g' hdag.yaml
            perl -pi -e 's/{INTERNAL_IP}/127.0.0.1/g' hdag.yaml

            perl -pi -e 's;test/hello-world;demo0/hello-world;g' hdag.yaml

            perl -pi -e 's;version: '1.0.0';version: '0.1.0';g' hdag.yaml

            cd {DEMO}/hello-world/templates
            # perl -pi -e 's/127.0.0.1/{INTERNAL_IP}/g' deployment.yaml
            # perl -pi -e 's/127.0.0.1/localhost/g' deployment.yaml
            perl -pi -e 's/127.0.0.1/{eth0}/g' deployment.yaml
            """
        ],
        _get_pty=True,
        _shell_executable="/bin/bash",
    )

    server.shell(
        name=f"Prepare {GRAPH_NAME}",
        commands=[
            f"""
            cd {TOP_DIR}
            . .venv/bin/activate

            cd {DEMO}
            inv prepare
            """
        ],
        _get_pty=True,
        _shell_executable="/bin/bash",
    )


def deploy_on_smo() -> None:
    DESCRIPTOR = f"{DEMO}/hdag/hdag.yaml"
    result = server.shell(
        name=f"Deploy {GRAPH_NAME}",
        commands=[
            f"""
            cd {REPO}
            . .venv/bin/activate

            export KUBECONFIG="/root/.kube/karmada-apiserver.config"
            kubectl config use-context karmada-apiserver

            {SMO_CLI} graph deploy --project {PROJECT} {DESCRIPTOR}
        """,
        ],
        _get_pty=True,
        _shell_executable="/bin/bash",
    )
    python.call(
        name=f"Show deploying {GRAPH_NAME}",
        function=log_callback,
        result=result,
    )


def smo_show_graph_list() -> None:
    result = server.shell(
        name="Exec smo-cli graph list",
        commands=[
            f"""\
            cd {REPO}
            . .venv/bin/activate

            export KUBECONFIG="/root/.kube/karmada-apiserver.config"
            kubectl config use-context karmada-apiserver

            echo "graph list:"
            smo-cli graph list
            """
        ],
        _shell_executable="/bin/bash",
        _get_pty=True,
    )
    python.call(
        name="Show smo-cli graph list",
        function=log_callback,
        result=result,
    )


# def check_clusters() -> None:
#     cmd = make_clusters_list_command()
#     result = server.shell(
#         name="Get clusters list",
#         commands=[cmd],
#         _get_pty=True,
#         _shell_executable="/bin/bash",
#     )
#     python.call(
#         name="Show clusters list",
#         function=log_callback,
#         result=result,
#     )


def find_kubernetes_pods() -> None:
    for context in (
        # "karmada-host",
        # "karmada-apiserver",
        "member1",
        # "member2",
    ):
        result = server.shell(
            name=f"Find kubernetes pods in {context!r}",
            commands=[
                f"""
            export KUBECONFIG="/root/.kube/karmada-apiserver.config"
            kubectl config use-context {context}

            kubectl get pods -A
            """
            ],
            _get_pty=True,
            _shell_executable="/bin/bash",
        )
        python.call(
            name=f"Show kubernetes pods in {context!r}",
            function=log_callback,
            result=result,
        )


def find_demo0() -> None:
    result = server.shell(
        name="Find demo0 in member1",
        commands=[
            """
            export KUBECONFIG="/root/.kube/karmada-apiserver.config"
            kubectl config use-context member1

            pod_name=$(kubectl get pods -n demo0 -o jsonpath='{.items[0].metadata.name}')
            kubectl wait --for=condition=Ready pod/$pod_name -n demo0 --timeout=120s
            kubectl port-forward -n demo0 $pod_name 8080:8080 &
            sleep 2
            counter=0
            code=""
            while [ $counter -lt 120 ]; do
                code=$(curl -s -o /dev/null -w "%{http_code}" "http://localhost:8080")
                if [ "$code" -eq 200 ]; then
                    break
                fi
                counter=$((counter + 2))
                sleep 2
            done

            echo "curl -s http://localhost:8080"
            curl -s http://localhost:8080
            echo

        """
        ],
        _get_pty=True,
        _shell_executable="/bin/bash",
    )
    python.call(
        name="Show demo0 response in member1",
        function=log_callback,
        result=result,
    )


main()
