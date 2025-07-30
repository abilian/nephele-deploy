"""
Minimal recipe to install smo nephele

assuming 0-setup-server.py has already been applied for base packages.

Warning: connection as user root.

pyinfra -y -v --user root ${SERVER_NAME} 10-install-nephele-smo.py
"""

# from pyinfra import host
# from pyinfra.facts.files import File
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
        name="Replace IP in smo files",
        commands=[
            f"""\
                cd {REPO}
                . .venv/bin/activate
                cd {DEMO}
                perl -pi -e 's/10.0.3.53/{LOCAL_IP}/g' Makefile
                perl -pi -e 's/10.0.3.53/{LOCAL_IP}/g' create-existing-artifact.sh
                perl -pi -e 's/10.0.3.53/{LOCAL_IP}/g' create-existing-artifact.sh
                cd {DEMO}/hdag
                perl -pi -e 's/10.0.3.53/{LOCAL_IP}/g' hdag.yaml
                cd {DEMO}/image-compression-vo/templates
                perl -pi -e 's/10.0.3.53/{LOCAL_IP}/g' /deployment.yaml
                cd {DEMO}/image-detection/templates
                perl -pi -e 's/10.0.3.53/{LOCAL_IP}/g' /deployment.yaml
                cd {DEMO}/noise-reduction/templates
                perl -pi -e 's/10.0.3.53/{LOCAL_IP}/g' /deployment.yaml
            """
        ],
        _shell_executable="/bin/bash",
        _get_pty=True,
    )

    server.shell(
        name="Replace IP in smo config (dubious)",
        commands=[
            # f"""\
            #     cd {REPO}
            #     . .venv/bin/activate
            #     cd config
            #     perl -pi -e 's/10.0.3.53/{LOCAL_IP}/g' flask.env
            # """
            f"""\
                cd {REPO}
                . .venv/bin/activate

                export KUBECONFIG="/root/.kube/karmada.config"
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


# (smo) root@ubuntu-16gb-hel1-4:~/gits/smo# kubectl get services --all-namespaces
# NAMESPACE        NAME                                                 TYPE        CLUSTER-IP      EXTERNAL-IP   PORT(S)                         AGE
# default          kubernetes                                           ClusterIP   10.96.0.1       <none>        443/TCP                         15m
# karmada-system   etcd                                                 ClusterIP   None            <none>        2379/TCP,2380/TCP               14m
# karmada-system   etcd-client                                          ClusterIP   10.96.35.209    <none>        2379/TCP                        14m
# karmada-system   karmada-aggregated-apiserver                         ClusterIP   10.96.168.250   <none>        443/TCP                         14m
# karmada-system   karmada-apiserver                                    ClusterIP   10.96.8.254     <none>        5443/TCP                        14m
# karmada-system   karmada-metrics-adapter                              ClusterIP   10.96.234.23    <none>        443/TCP                         14m
# karmada-system   karmada-scheduler-estimator-member1                  ClusterIP   10.96.139.34    <none>        10352/TCP                       13m
# karmada-system   karmada-scheduler-estimator-member2                  ClusterIP   10.96.181.120   <none>        10352/TCP                       13m
# karmada-system   karmada-scheduler-estimator-member3                  ClusterIP   10.96.118.228   <none>        10352/TCP                       13m
# karmada-system   karmada-search                                       ClusterIP   10.96.189.11    <none>        443/TCP                         14m
# karmada-system   karmada-webhook                                      ClusterIP   10.96.49.202    <none>        443/TCP                         14m
# kube-system      kube-dns                                             ClusterIP   10.96.0.10      <none>        53/UDP,53/TCP,9153/TCP          15m
# kube-system      prometheus-kube-prometheus-coredns                   ClusterIP   None            <none>        9153/TCP                        13m
# kube-system      prometheus-kube-prometheus-kube-controller-manager   ClusterIP   None            <none>        10257/TCP                       13m
# kube-system      prometheus-kube-prometheus-kube-etcd                 ClusterIP   None            <none>        2381/TCP                        13m
# kube-system      prometheus-kube-prometheus-kube-proxy                ClusterIP   None            <none>        10249/TCP                       13m
# kube-system      prometheus-kube-prometheus-kube-scheduler            ClusterIP   None            <none>        10259/TCP                       13m
# kube-system      prometheus-kube-prometheus-kubelet                   ClusterIP   None            <none>        10250/TCP,10255/TCP,4194/TCP    13m
# monitoring       alertmanager-operated                                ClusterIP   None            <none>        9093/TCP,9094/TCP,9094/UDP      13m
# monitoring       prometheus-grafana                                   ClusterIP   10.96.254.138   <none>        80/TCP                          13m
# monitoring       prometheus-kube-prometheus-alertmanager              NodePort    10.96.41.42     <none>        9093:30093/TCP,8080:31646/TCP   13m
# monitoring       prometheus-kube-prometheus-operator                  ClusterIP   10.96.244.43    <none>        443/TCP                         13m
# monitoring       prometheus-kube-prometheus-prometheus                NodePort    10.96.168.251   <none>        9090:30090/TCP,8080:32598/TCP   13m
# monitoring       prometheus-kube-state-metrics                        ClusterIP   10.96.79.234    <none>        8080/TCP                        13m
# monitoring       prometheus-operated                                  ClusterIP   None            <none>        9090/TCP                        13m
# monitoring       prometheus-prometheus-node-exporter                  ClusterIP   10.96.33.93     <none>        9100/TCP                        13m


def start_smo() -> None:
    result = server.shell(
        name="Start smo",
        commands=[
            f"""\
                cd {REPO}
                . .venv/bin/activate
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
