"""
Minimal recipe to install smo nephele

assuming 0-setup-server.py has already been applied for base packages.

Warning: connection as user root.

pyinfra -y -v --user root ${SERVER_NAME} 10-install-nephele-smo.py
"""

from pyinfra.operations import files, python, server

from common import log_callback
from constants import GITS

SMO_NEPHE = "smo"
SMO_NEPHE_URL = (
    "https://gitlab.eclipse.org/eclipse-research-labs/nephele-project/smo.git"
)
SMO_CLI = "/usr/local/bin/smo-cli"
BRANCH = "main"
LOCAL_IP = "127.0.0.1"
INTERNAL_IP = "host.docker.internal"
REPO = f"{GITS}/{SMO_NEPHE}"


def main() -> None:
    remove_prior_smo_cli()
    install_smo()
    # make_smo_tests()
    configure_smo_ip()
    start_smo()


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
        name=f"Clone/pull {SMO_NEPHE} source",
        commands=[
            f"[ -d {REPO} ] || git clone {SMO_NEPHE_URL} {REPO}",
            f"""
                cd {REPO}
                git fetch
                git clean -fxd
                git checkout {BRANCH}
                git reset --hard HEAD
            """,
        ],
        _shell_executable="/bin/bash",
        _get_pty=True,
    )

    files.put(
        name="Put smo patch file",
        src="fix/kind.patch",
        dest="/root/gits/smo/kind.patch",
        mode="644",
    )

    server.shell(
        name="Apply patch to smo",
        commands=[
            f"[ -d {REPO} ] || git clone {SMO_NEPHE_URL} {REPO}",
            f"""
                cd {REPO}
                git apply kind.patch
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
                make
            """
        ],
        _shell_executable="/bin/bash",
        _get_pty=True,
    )


def configure_smo_ip() -> None:
    server.shell(
        name="Replace IP in smo config",
        commands=[
            f"""\
                cd {REPO}
                . .venv/bin/activate

                export KUBECONFIG="/root/.kube/karmada-apiserver.config"
                kubectl config use-context karmada-host
                # kubectl get services --all-namespaces

                # this is the cluster NodePort ip:
                # prom_ip=$(kubectl get service prometheus-kube-prometheus-prometheus -n monitoring -o jsonpath='{{.spec.clusterIP}}')

                kind_node_ip=$(docker inspect -f '{{{{range.NetworkSettings.Networks}}}}{{{{.IPAddress}}}}{{{{end}}}}' karmada-host-control-plane)

                cd config
                perl -pi -e "s/10.0.3.53/${{kind_node_ip}}/g" flask.env
            """
        ],
        _shell_executable="/bin/bash",
        _get_pty=True,
    )

    result = server.shell(
        name="get grafana IP and password",
        commands=[
            f"""
            cd {REPO}
            . .venv/bin/activate

            export KUBECONFIG="/root/.kube/karmada-apiserver.config"
            kubectl config use-context karmada-host

            # Use the grafana installed by prometheus:
            kubectl -n monitoring get svc prometheus-grafana
            central_node_ip=$(kubectl get nodes -o jsonpath='{{.items[0].status.addresses[?(@.type=="InternalIP")].address}}')
            node_port=$(kubectl -n monitoring get svc prometheus-grafana -o jsonpath='{{.spec.ports[0].nodePort}}')
            grafana_url="http://${{central_node_ip}}:${{node_port}}"
            echo "Grafana URL: ${{grafana_url}}"
            curl ${{grafana_url}}

            # replace in smo config
            cd config
            perl -pi -e "s;GRAFANA_HOST.*;GRAFANA_HOST='${{grafana_url}}';g" flask.env
            """
        ],
        _shell_executable="/bin/bash",
        _get_pty=True,
    )
    python.call(
        name="Show grafana informations",
        function=log_callback,
        result=result,
    )


def start_smo() -> None:
    result = server.shell(
        name="Fix .doker access",
        commands=[
            """\
                chmod 777 /root/.docker
                chmod a+rw /root/.docker/*
            """
        ],
        _shell_executable="/bin/bash",
        _get_pty=True,
    )
    python.call(
        name="Show staet smo",
        function=log_callback,
        result=result,
    )

    result = server.shell(
        name="Start smo",
        commands=[
            f"""\
                cd {REPO}
                . .venv/bin/activate

                docker compose down -v --rmi all

                docker compose -f docker-compose.yml up -d
            """
        ],
        _shell_executable="/bin/bash",
        _get_pty=True,
    )
    python.call(
        name="Show start smo",
        function=log_callback,
        result=result,
    )


main()
