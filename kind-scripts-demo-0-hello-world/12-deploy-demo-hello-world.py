"""
Minimal recipe build for the hello-world app.

Warning: connection as user root.

pyinfra -y -v --user root ${SERVER_NAME} 12-deploy-demo-hello-world.py
"""

from pyinfra.operations import server, python
from common import log_callback

from constants import GITS

TOP_DIR = f"{GITS}/h3ni-demos/"
SMO_URL = "http://127.0.0.1:8000"
REGISTRY_URL = "http://host.docker.internal:5000"
DEMO = f"{GITS}/h3ni-demos/0-hello-world-demo"
PROJECT = "demo0"
GRAPH_NAME = "hello-world-graph"


def make_graph_delete_cmd(graph: str) -> str:
    return f"curl -X DELETE {SMO_URL}/graphs/{graph}"


def make_deploy_command(project: str, graph: str) -> str:
    data = f'{{"artifact": "{REGISTRY_URL}/{project}/{graph}"}}'
    cmd = (
        f'curl -X POST "{SMO_URL}/project/{project}/graphs" '
        '-H "Content-Type: application/json" '
        f"--data '{data}'"
    )
    return cmd


def make_graph_list_command(project: str) -> str:
    return f'curl -X GET "{SMO_URL}/project/{project}/graphs"'


def make_clusters_list_command() -> str:
    return f'curl -X GET "{SMO_URL}/clusters/"'


def main() -> None:
    clean_installed_graphs()
    prepare_hello_world()
    deploy_on_smo()
    check_graph_list()
    check_clusters()
    find_kubernetes_pods()


def clean_installed_graphs() -> None:
    for name in ("hello-world-graph", "image-detection-graph"):
        cmd = make_graph_delete_cmd(name)
        server.shell(
            name=f"Remove prior known graph {name}",
            # commands=[(f"yes | {SMO_CLI} graph remove {name} || true")],
            commands=[f"{cmd} || true"],
            _get_pty=True,
            _shell_executable="/bin/bash",
        )


def prepare_hello_world() -> None:
    server.shell(
        name="Prepare hello-world-graph",
        commands=[
            (
                f"""
                cd {TOP_DIR}
                . .venv/bin/activate

                cd {DEMO}
                inv prepare
                """
            )
        ],
        _get_pty=True,
        _shell_executable="/bin/bash",
    )


def deploy_on_smo() -> None:
    cmd = make_deploy_command(PROJECT, GRAPH_NAME)
    result = server.shell(
        name="Deploy hello-world-graph to smo",
        commands=[cmd],
        _get_pty=True,
        _shell_executable="/bin/bash",
    )
    python.call(
        name="Show deploying hello-world-graph",
        function=log_callback,
        result=result,
    )


def check_graph_list() -> None:
    cmd = make_graph_list_command(PROJECT)
    result = server.shell(
        name="Get graph list",
        commands=[cmd],
        _get_pty=True,
        _shell_executable="/bin/bash",
    )
    python.call(
        name="Show graph list",
        function=log_callback,
        result=result,
    )


def check_clusters() -> None:
    cmd = make_clusters_list_command()
    result = server.shell(
        name="Get clusters list",
        commands=[cmd],
        _get_pty=True,
        _shell_executable="/bin/bash",
    )
    python.call(
        name="Show clusters list",
        function=log_callback,
        result=result,
    )


def find_kubernetes_pods() -> None:
    for context in (
        "karmada-host",
        "karmada-apiserver",
        "member1",
        "member2",
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


main()
