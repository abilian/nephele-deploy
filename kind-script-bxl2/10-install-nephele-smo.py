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
REPO = f"{GITS}/{SMO_NEPHE}"
DEMO = f"{REPO}/examples/brussels-demo/"

SMO_PATCH = """\
diff --git a/docker-compose.yml b/docker-compose.yml
index 43f8ca1..b8108c4 100644
--- a/docker-compose.yml
+++ b/docker-compose.yml
@@ -3,6 +3,8 @@ services:
     restart: always
     container_name: smo
     build: .
+    extra_hosts:
+      - "host.docker.internal:host-gateway"
     env_file:
     - config/flask.env
     volumes:
@@ -17,14 +19,18 @@ services:
     depends_on:
       postgres:
         condition: service_healthy
+    networks:
+      - kind
+      #- smo-net
     ports:
-      - 8000:8000
-    extra_hosts:
-    - "host.docker.internal:host-gateway"
+      - "8000:8000"
   postgres:
     restart: always
     container_name: postgres
     image: postgres:16.2
+    networks:
+      - kind
+      #- smo-net
     env_file:
     - config/postgres.env
     healthcheck:
@@ -33,3 +39,8 @@ services:
       timeout: 3s
       retries: 3
       start_period: 3s
+networks:
+  kind:
+    external: true
+  #smo-net:
+  #  driver: bridge
diff --git a/src/utils/karmada_helper.py b/src/utils/karmada_helper.py
index d8775e9..8b6d85d 100644
--- a/src/utils/karmada_helper.py
+++ b/src/utils/karmada_helper.py
@@ -14,7 +14,17 @@ class KarmadaHelper():
         self.namespace = namespace
         self.config_file_path = config_file_path

-        config.load_kube_config(config_file=self.config_file_path)
+        KARMADA_CONTEXT_NAME = "karmada-apiserver"
+
+        try:
+            config.load_kube_config(config_file=self.config_file_path, context=KARMADA_CONTEXT_NAME)
+            print(f"Successfully loaded kubeconfig for context: {KARMADA_CONTEXT_NAME}")
+        except config.ConfigException as e:
+            print(f"ERROR: Failed to load Karmada kubeconfig context '{KARMADA_CONTEXT_NAME}': {e}")
+            print("Check ~/.kube/karmada-apiserver.config file has the 'karmada-apiserver' context.")
+            raise
+
+		#config.load_kube_config(config_file=self.config_file_path)

         self.custom_api = client.CustomObjectsApi()
         self.v1_api_client = client.AppsV1Api()
"""


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

    server.shell(
        name="Patch smo for kid compatibility",
        commands=[
            f"cd {GITS}/smo && echo '{SMO_PATCH}' | git apply",
        ],
        _shell_executable="/bin/bash",
        _get_pty=True,
        _ignore_errors=True,
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
                perl -pi -e 's/10.0.3.53/{LOCAL_IP}/g' hdag.yaml
                cd {DEMO}/image-compression-vo/templates
                perl -pi -e 's/10.0.3.53/{LOCAL_IP}/g' deployment.yaml
                cd {DEMO}/image-detection/templates
                perl -pi -e 's/10.0.3.53/{LOCAL_IP}/g' deployment.yaml
                cd {DEMO}/noise-reduction/templates
                perl -pi -e 's/10.0.3.53/{LOCAL_IP}/g' deployment.yaml

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
    # server.shell(
    #     name="Install missing grafana",
    #     commands=[
    #         """
    #             export KUBECONFIG="/root/.kube/karmada-apiserver.config"
    #             kubectl config use-context karmada-host

    #             helm repo add grafana https://grafana.github.io/helm-charts
    #             helm repo update

    #             helm install grafana grafana/grafana \
    #             --namespace monitoring --create-namespace \
    #             --set service.type=NodePort \
    #             --set service.nodePort=31802
    #         """
    #     ],
    #     _shell_executable="/bin/bash",
    #     _get_pty=True,
    # )

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


# Traceback (most recent call last):
#   File "/app/.venv/lib/python3.11/site-packages/flask/app.py", line 1536, in __call__
#     return self.wsgi_app(environ, start_response)
#            ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
#   File "/app/.venv/lib/python3.11/site-packages/flask/app.py", line 1514, in wsgi_app
#     response = self.handle_exception(e)
#                ^^^^^^^^^^^^^^^^^^^^^^^^
#   File "/app/.venv/lib/python3.11/site-packages/flask/app.py", line 1511, in wsgi_app
#     response = self.full_dispatch_request()
#                ^^^^^^^^^^^^^^^^^^^^^^^^^^^^
#   File "/app/.venv/lib/python3.11/site-packages/flask/app.py", line 919, in full_dispatch_request
#     rv = self.handle_user_exception(e)
#          ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
#   File "/app/.venv/lib/python3.11/site-packages/flask/app.py", line 917, in full_dispatch_request
#     rv = self.dispatch_request()
#          ^^^^^^^^^^^^^^^^^^^^^^^
#   File "/app/.venv/lib/python3.11/site-packages/flask/app.py", line 902, in dispatch_request
#     return self.ensure_sync(self.view_functions[rule.endpoint])(**view_args)  # type: ignore[no-any-return]
#            ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
#   File "/app/.venv/lib/python3.11/site-packages/flasgger/utils.py", line 305, in wrapper
#     return function(*args, **kwargs)
#            ^^^^^^^^^^^^^^^^^^^^^^^^^
#   File "/app/src/routes/hdag/graph.py", line 37, in deploy
#     graph_descriptor = descriptor['hdaGraph']
#                        ^^^^^^^^^^^^^^^^^^^^^^
# TypeError: 'NoneType' object is not subscriptable
