"""
Minimal recipe build for the hello-world app.

Warning: connection as user root.

pyinfra -y -v --user root ${SERVER_NAME} 14-deploy-demo-2
"""

from pyinfra import host
from pyinfra.facts.hardware import Ipv4Addrs
from pyinfra.operations import files, python, server

from common import log_callback
from constants import GITS

TOP_DIR = f"{GITS}/h3ni-demos/"
SMO_URL = "http://127.0.0.1:8000"
REGISTRY_URL = "http://host.docker.internal:5000"
DEMO = f"{GITS}/h3ni-demos/2-gpu-offloading-demo"
PROJECT = "demo2"
GRAPH_NAME = "gpu-offloading-graph"
INTERNAL_IP = "host.docker.internal"


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
    change_hdag_file()
    prepare_gpu_offloading()
    deploy_on_smo()
    check_graph_list()
    check_clusters()
    find_kubernetes_pods()
    find_demo2()


def clean_installed_graphs() -> None:
    for name in ("hello-world-graph", "image-detection-graph", "gpu-offloading-graph"):
        cmd = make_graph_delete_cmd(name)
        server.shell(
            name=f"Remove prior known graph {name}",
            # commands=[(f"yes | {SMO_CLI} graph remove {name} || true")],
            commands=[f"{cmd} || true"],
            _get_pty=True,
            _shell_executable="/bin/bash",
        )


def change_hdag_file() -> None:
    files.put(
        name="Put hdag file",
        src="hdag.yaml",
        dest="/root/gits/h3ni-demos/2-gpu-offloading-demo/hdag/hdag.yaml",
        mode="644",
    )


def prepare_gpu_offloading() -> None:
    ips = host.get_fact(Ipv4Addrs)
    eth0 = ips["eth0"][0]
    server.shell(
        name="Fix image name and address",
        commands=[
            f"""
            cd {DEMO}/hdag

            perl -pi -e 's/127.0.0.1/{INTERNAL_IP}/g' hdag.yaml

            perl -pi -e 's;test/web-frontend;demo2/web-frontend;g' hdag.yaml
            perl -pi -e 's;test/ml-inference;demo2/ml-inference;g' hdag.yaml

            perl -pi -e 's;version: '1.0.0';version: '0.1.0';g' hdag.yaml

            cd {DEMO}/web-frontend/templates
            perl -pi -e 's/127.0.0.1/{eth0}/g' deployment.yaml
            """
        ],
        _get_pty=True,
        _shell_executable="/bin/bash",
    )

    server.shell(
        name="Prepare gpu offloading graph",
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
    cmd = make_deploy_command(PROJECT, GRAPH_NAME)
    result = server.shell(
        name="Deploy gpu-offloading to smo",
        commands=[cmd],
        _get_pty=True,
        _shell_executable="/bin/bash",
    )
    python.call(
        name="Show deploying gpu-offloading",
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


def find_demo2() -> None:
    result = server.shell(
        name="Find demo2 in member1",
        commands=[
            """
            export KUBECONFIG="/root/.kube/karmada-apiserver.config"
            kubectl config use-context member1

            pod_name=$(kubectl get pods -n demo2 -o jsonpath='{.items[0].metadata.name}')
            kubectl wait --for=condition=Ready pod/$pod_name -n demo2 --timeout=120s
            kubectl port-forward -n demo2 $pod_name 8080:8080 &
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
        name="Show demo2 response in member1",
        function=log_callback,
        result=result,
    )


main()
