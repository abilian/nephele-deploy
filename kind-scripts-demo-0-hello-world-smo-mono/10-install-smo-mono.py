"""
Minimal recipe to install smo-monorepo

Warning: connection as user root.

pyinfra -y -v --user root ${SERVER_NAME} 10-install-smo-monorepo.py
"""

from pyinfra.operations import files, python, server

from common import log_callback
from constants import GITS

SMO_MONO = "smo-monorepo"
SMO_MONO_URL = (
    "https://gitlab.eclipse.org/eclipse-research-labs/"
    "nephele-project/opencall-2/h3ni/smo-monorepo.git"
)
BRANCH = "main"
LOCAL_IP = "127.0.0.1"
INTERNAL_IP = "host.docker.internal"
REPO = f"{GITS}/{SMO_MONO}"
SMO_CLI = "/usr/local/bin/smo-cli"


def main() -> None:
    remove_prior_smo_cli()
    install_smo()
    # make_smo_tests()
    init_smo()
    smo_cluster_sync()
    smo_show_graph()


def remove_prior_smo_cli() -> None:
    files.file(
        name=f"Remove {SMO_CLI} if exists",
        path=SMO_CLI,
        present=False,
        force=True,
    )


def install_smo() -> None:
    files.directory(
        name=f"Create {GITS} directory",
        path=GITS,
    )

    server.shell(
        name=f"Clone/pull {SMO_MONO} source",
        commands=[
            f"[ -d {REPO} ] || git clone {SMO_MONO_URL} {REPO}",
            f"""
                cd {REPO}
                git clean -fxd
                git reset --hard HEAD
                git pull
                git checkout {BRANCH}
            """,
        ],
        _shell_executable="/bin/bash",
        _get_pty=True,
    )

    server.shell(
        name="Build smo",
        commands=[
            f"""
                cd {REPO}
                uv venv --clear -p3.12
                . .venv/bin/activate

                uv sync
            """
        ],
        _shell_executable="/bin/bash",
        _get_pty=True,
    )


def make_smo_tests() -> None:
    server.shell(
        name="make smo tests",
        commands=[
            f"""
                cd {REPO}
                . .venv/bin/activate

                make test
            """
        ],
        _shell_executable="/bin/bash",
        _get_pty=True,
    )


def init_smo() -> None:
    server.shell(
        name=f"Copy smo-cli to {SMO_CLI}",
        commands=[
            f"""
                cp -f {REPO}/.venv/bin/smo-cli {SMO_CLI}
            """
        ],
        _shell_executable="/bin/bash",
        _get_pty=True,
    )

    server.shell(
        name="Init smo",
        commands=[
            f"""
            cd {REPO}
            . .venv/bin/activate

            export KUBECONFIG="/root/.kube/karmada-apiserver.config"
            kubectl config use-context karmada-apiserver

            {SMO_CLI} init
            """
        ],
        _shell_executable="/bin/bash",
        _get_pty=True,
    )

    server.shell(
        name="Replace IPs in smo config",
        commands=[
            f"""
            cd {REPO}
            . .venv/bin/activate

            # export KUBECONFIG="/root/.kube/karmada-apiserver.config"
            # kubectl config use-context karmada-apiserver
            # kubectl get services --all-namespaces

            # this is the cluster NodePort ip:
            # prom_ip=$(kubectl get service prometheus-kube-prometheus-prometheus -n monitoring -o jsonpath='{{.spec.clusterIP}}')

            # get grafana address from outside cluster
            export KUBECONFIG="/root/.kube/karmada-apiserver.config"
            kubectl config use-context karmada-host

            kind_node_ip=$(docker inspect -f '{{{{range.NetworkSettings.Networks}}}}{{{{.IPAddress}}}}{{{{end}}}}' karmada-host-control-plane)
            grafana_port=$(kubectl get svc -n monitoring prometheus-grafana -o jsonpath='{{.spec.ports[?(@.name=="http-web")].nodePort}}')

            cd /root/.smo
            perl -pi -e "s;  host: http://.*;  host: http://${{kind_node_ip}}:${{grafana_port}};g" config.yaml
            """
        ],
        _shell_executable="/bin/bash",
        _get_pty=True,
    )


def smo_cluster_sync() -> None:
    result = server.shell(
        name="Exec smo-cli cluster sync",
        commands=[
            f"""
            cd {REPO}
            . .venv/bin/activate

            export KUBECONFIG="/root/.kube/karmada-apiserver.config"
            kubectl config use-context karmada-apiserver

            smo-cli cluster sync
            """,
        ],
        _shell_executable="/bin/bash",
        _get_pty=True,
    )
    python.call(
        name="Show smo-cli cluster sync",
        function=log_callback,
        result=result,
    )


def smo_show_graph() -> None:
    result = server.shell(
        name="Exec smo-cli graph list",
        commands=[
            f"""
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


main()
