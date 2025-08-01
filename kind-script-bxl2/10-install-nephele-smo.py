"""
Minimal recipe to install smo nephele

assuming 0-setup-server.py has already been applied for base packages.

Warning: connection as user root.

pyinfra -y -v --user root ${SERVER_NAME} 10-install-nephele-smo.py
"""

import io

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
DEMO = f"{REPO}/examples/brussels-demo/"


def main() -> None:
    remove_prior_smo_cli()
    install_smo()
    # make_smo_tests()
    replace_ip()
    start_smo()
    make_brussels_demo_images()
    show_docker_images()
    check_images()
    make_package_artifacts()
    make_push_artifacts()
    create_existing_artifacts()


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
                git checkout {BRANCH}
                git reset --hard HEAD
                git pull
            """,
        ],
        _shell_executable="/bin/bash",
        _get_pty=True,
    )

    files.put(
        name="Put smo fix",
        src="fix/karmada_helper.py",
        dest="/root/gits/smo/src/utilsl/karmada_helper.py",
        mode="644",
    )

    files.put(
        name="Put fixed docker compose file",
        src="fix/docker-compose.yml",
        dest="/root/gits/smo/docker-compose.yml",
        mode="644",
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


def replace_ip() -> None:
    server.shell(
        name="Reset config files",
        commands=[
            f"""\
                cd {REPO}
                . .venv/bin/activate
                cd {DEMO}
                git restore -- Makefile
                git restore -- create-existing-artifact.sh
                cd {DEMO}/hdag
                git restore --  hdag.yaml
                cd {DEMO}/image-compression-vo/templates
                git restore -- deployment.yaml
                cd {DEMO}/image-detection/templates
                git restore -- deployment.yaml
                cd {DEMO}/noise-reduction/templates
                git restore -- deployment.yaml
                cd {REPO}/config
                git restore -- flask.env
            """
        ],
        _shell_executable="/bin/bash",
        _get_pty=True,
    )

    server.shell(
        name="Restore config files",
        commands=[
            f"""\
                cd {REPO}
                . .venv/bin/activate

                cd {DEMO}
                perl -pi -e 's/10.0.3.53/{LOCAL_IP}/g' Makefile
                perl -pi -e 's/10.0.3.53/{LOCAL_IP}/g' create-existing-artifact.sh
                cd {DEMO}/hdag
                perl -pi -e 's/10.0.3.53/{INTERNAL_IP}/g' hdag.yaml
                cd {DEMO}/image-compression-vo/templates
                perl -pi -e 's/10.0.3.53/{INTERNAL_IP}/g' deployment.yaml
                cd {DEMO}/image-detection/templates
                perl -pi -e 's/10.0.3.53/{INTERNAL_IP}/g' deployment.yaml
                cd {DEMO}/noise-reduction/templates
                perl -pi -e 's/10.0.3.53/{INTERNAL_IP}/g' deployment.yaml

                cd {DEMO}
                perl -pi -e 's;REGISTRY_URL=.*;REGISTRY_URL="http://host.docker.internal:5000";g' create-existing-artifact.sh


            """
        ],
        _shell_executable="/bin/bash",
        _get_pty=True,
    )

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

            # pwd=$(kubectl get secret --namespace monitoring prometheus-grafana \
            # -o jsonpath="{{.data.admin-password}}" | base64 --decode)

            # echo "grafana pwd: ${{pwd}}"

            # central_node_ip=$(kubectl get nodes -o jsonpath='{{.items[0].status.addresses[?(@.type=="InternalIP")].address}}')
            # grafana_url="http://${{central_node_ip}}:31802"
            # echo "Grafana URL: ${{grafana_url}}"

            # curl ${{grafana_url}}

            # Use the grafana installed by prometheus:

            kubectl -n monitoring get svc prometheus-grafana
            central_node_ip=$(kubectl get nodes -o jsonpath='{{.items[0].status.addresses[?(@.type=="InternalIP")].address}}')
            node_port=$(kubectl -n monitoring get svc prometheus-grafana -o jsonpath='{{.spec.ports[0].nodePort}}')
            grafana_url="http://${{central_node_ip}}:${{node_port}}"
            echo "Grafana URL: ${{grafana_url}}"
            curl ${{grafana_url}}

            # replace in smo config
            cd config
            # perl -pi -e "s/GRAFANA_PASSWORD.*/GRAFANA_PASSWORD='${{pwd}}'/g" flask.env
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


# (smo) root@ubuntu-16gb-hel1-4:~/gits/smo# kubectl get services --all-namespaces


def start_smo() -> None:
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
        name="Show staet smo",
        function=log_callback,
        result=result,
    )


def make_brussels_demo_images() -> None:
    server.shell(
        name="Make brussels images",
        commands=[
            f"""\
                cd {REPO}
                . .venv/bin/activate
                cd {DEMO}
                make build-images && make push-images
            """
        ],
        _shell_executable="/bin/bash",
        _get_pty=True,
    )


def show_docker_images() -> None:
    result = server.shell(
        name="Show brussels images",
        commands=["docker images"],
    )
    python.call(
        name="Show brussels images",
        function=log_callback,
        result=result,
    )


def check_images() -> None:
    result = server.shell(
        name="Check images in local docker registry",
        commands=[
            "curl -s -X GET http://localhost:5000/v2/_catalog",
        ],
    )
    python.call(
        name="Show Check images in local docker registry",
        function=log_callback,
        result=result,
    )


# def make_registry_login() -> None:
#     result = server.shell(
#         name="Make registry login",
#         commands=[
#             f"""\
#                 cd {REPO}
#                 . .venv/bin/activate
#                 cd {DEMO}
#                 make registry-login
#             """,
#         ],
#         _shell_executable="/bin/bash",
#         _get_pty=True,
#     )
#     python.call(
#         name="Show registry login",
#         function=log_callback,
#         result=result,
#     )


def make_package_artifacts() -> None:
    result = server.shell(
        name="Make package artifacts",
        commands=[
            f"""\
                cd {REPO}
                . .venv/bin/activate
                cd {DEMO}
                make package-artifacts
            """,
        ],
        _shell_executable="/bin/bash",
        _get_pty=True,
    )
    python.call(
        name="Show package artifacts",
        function=log_callback,
        result=result,
    )


def make_push_artifacts() -> None:
    result = server.shell(
        name="Make push artifacts",
        commands=[
            f"""\
                cd {REPO}
                . .venv/bin/activate
                cd {DEMO}
                make push-artifacts
            """,
        ],
        _shell_executable="/bin/bash",
        _get_pty=True,
    )
    python.call(
        name="Show push artifacts",
        function=log_callback,
        result=result,
    )


def create_existing_artifacts() -> None:
    result = server.shell(
        name="Run create-existing-artifact.sh",
        commands=[
            f"""\
                cd {REPO}
                . .venv/bin/activate

                cd {DEMO}

                docker compose ps smo

                bash create-existing-artifact.sh
            """,
        ],
        _shell_executable="/bin/bash",
        _get_pty=True,
    )
    python.call(
        name="Show create-existing-artifact.sh output",
        function=log_callback,
        result=result,
    )


main()

# smo  | Traceback (most recent call last):
# smo  |   File "/app/.venv/bin/flask", line 10, in <module>
# smo  |     sys.exit(main())
# smo  |              ^^^^^^
# smo  |   File "/app/.venv/lib/python3.11/site-packages/flask/cli.py", line 1129, in main
# smo  |     cli.main()
# smo  |   File "/app/.venv/lib/python3.11/site-packages/click/core.py", line 1363, in main
# smo  |     rv = self.invoke(ctx)
# smo  |          ^^^^^^^^^^^^^^^^
# smo  |   File "/app/.venv/lib/python3.11/site-packages/click/core.py", line 1830, in invoke
# smo  |     return _process_result(sub_ctx.command.invoke(sub_ctx))
# smo  |                            ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
# smo  |   File "/app/.venv/lib/python3.11/site-packages/click/core.py", line 1226, in invoke
# smo  |     return ctx.invoke(self.callback, **ctx.params)
# smo  |            ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
# smo  |   File "/app/.venv/lib/python3.11/site-packages/click/core.py", line 794, in invoke
# smo  |     return callback(*args, **kwargs)
# smo  |            ^^^^^^^^^^^^^^^^^^^^^^^^^
# smo  |   File "/app/.venv/lib/python3.11/site-packages/click/decorators.py", line 93, in new_func
# smo  |     return ctx.invoke(f, obj, *args, **kwargs)
# smo  |            ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
# smo  |   File "/app/.venv/lib/python3.11/site-packages/click/core.py", line 794, in invoke
# smo  |     return callback(*args, **kwargs)
# smo  |            ^^^^^^^^^^^^^^^^^^^^^^^^^
# smo  |   File "/app/.venv/lib/python3.11/site-packages/flask/cli.py", line 977, in run_command
# smo  |     raise e from None
# smo  |   File "/app/.venv/lib/python3.11/site-packages/flask/cli.py", line 961, in run_command
# smo  |     app: WSGIApplication = info.load_app()  # pyright: ignore
# smo  |                            ^^^^^^^^^^^^^^^
# smo  |   File "/app/.venv/lib/python3.11/site-packages/flask/cli.py", line 353, in load_app
# smo  |     app = locate_app(import_name, None, raise_if_not_found=False)
# smo  |           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
# smo  |   File "/app/.venv/lib/python3.11/site-packages/flask/cli.py", line 262, in locate_app
# smo  |     return find_best_app(module)
# smo  |            ^^^^^^^^^^^^^^^^^^^^^
# smo  |   File "/app/.venv/lib/python3.11/site-packages/flask/cli.py", line 72, in find_best_app
# smo  |     app = app_factory()
# smo  |           ^^^^^^^^^^^^^
# smo  |   File "/app/src/app.py", line 48, in create_app
# smo  |     fetch_clusters(
# smo  |   File "/app/src/services/cluster/cluster_service.py", line 14, in fetch_clusters
# smo  |     karmada_cluster_info = karmada_helper.get_cluster_info()
# smo  |                            ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
# smo  |   File "/app/src/utils/karmada_helper.py", line 28, in get_cluster_info
# smo  |     clusters = self.custom_api.list_cluster_custom_object(group, version, plural)
# smo  |                ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
# smo  |   File "/app/.venv/lib/python3.11/site-packages/kubernetes/client/api/custom_objects_api.py", line 2090, in list_cluster_custom_object
# smo  |     return self.list_cluster_custom_object_with_http_info(group, version, plural, **kwargs)  # noqa: E501
# smo  |            ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
# smo  |   File "/app/.venv/lib/python3.11/site-packages/kubernetes/client/api/custom_objects_api.py", line 2221, in list_cluster_custom_object_with_http_info
# smo  |     return self.api_client.call_api(
# smo  |            ^^^^^^^^^^^^^^^^^^^^^^^^^
# smo  |   File "/app/.venv/lib/python3.11/site-packages/kubernetes/client/api_client.py", line 348, in call_api
# smo  |     return self.__call_api(resource_path, method,
# smo  |            ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
# smo  |   File "/app/.venv/lib/python3.11/site-packages/kubernetes/client/api_client.py", line 180, in __call_api
# smo  |     response_data = self.request(
# smo  |                     ^^^^^^^^^^^^^
# smo  |   File "/app/.venv/lib/python3.11/site-packages/kubernetes/client/api_client.py", line 373, in request
# smo  |     return self.rest_client.GET(url,
# smo  |            ^^^^^^^^^^^^^^^^^^^^^^^^^
# smo  |   File "/app/.venv/lib/python3.11/site-packages/kubernetes/client/rest.py", line 244, in GET
# smo  |     return self.request("GET", url,
# smo  |            ^^^^^^^^^^^^^^^^^^^^^^^^
# smo  |   File "/app/.venv/lib/python3.11/site-packages/kubernetes/client/rest.py", line 238, in request
# smo  |     raise ApiException(http_resp=r)
# smo  | kubernetes.client.exceptions.ApiException: (404)
# smo  | Reason: Not Found
# smo  | HTTP response headers: HTTPHeaderDict({'Audit-Id': 'f8a9634d-89b0-4288-b165-3d43bc700204', 'Cache-Control': 'no-cache, private', 'Content-Type': 'text/plain; charset=utf-8', 'X-Content-Type-Options': 'nosniff', 'X-Kubernetes-Pf-Flowschema-Uid': 'eaa48780-76ab-4a1e-998e-f6644fcc6a02', 'X-Kubernetes-Pf-Prioritylevel-Uid': '874ba548-0891-42e3-9182-a2e95048a2bf', 'Date': 'Fri, 01 Aug 2025 13:55:25 GMT', 'Content-Length': '19'})
# smo  | HTTP response body: 404 page not found
# smo  |
