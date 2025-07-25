"""
Minimal recipe to deploy kind kubernetes engine and tools on a ubuntu like distribution.

assuming 0-setup-server.py has already been applied for base packages.

pyinfra -y -vv --user root ${SERVER_NAME} 4-install-kubectl-karmada.py

Important fix:

kubectl apply -f - <<EOF
apiVersion: apiregistration.k8s.io/v1
kind: APIService
metadata:
  name: v1alpha1.cluster.karmada.io
spec:
  group: cluster.karmada.io
  version: v1alpha1
  service:
    name: karmada-aggregated-apiserver
    namespace: karmada-system
    port: 443
  groupPriorityMinimum: 2000
  versionPriority: 10
  insecureSkipTLSVerify: true
EOF

export KUBECONFIG=~/.kube/karmada.config
kubectl config use-context karmada-apiserver

Switched to context "karmada-apiserver".
kubectl config current-context   # should now show karmada-apiserver

kubectl get clusters
karmada-apiserver
NAME      VERSION   MODE   READY   AGE
member1   v1.31.2   Push   True    58m
member2   v1.31.2   Push   True    58m
member3   v1.31.2   Pull   True    58m



"""

from pyinfra import host
from pyinfra.facts.files import File
from pyinfra.operations import apt, files, python, server, snap, systemd

from common import log_callback
from constants import GITS


def main() -> None:
    delete_kind_clusters()
    git_clone_karmada()
    install_karmada_clusters()


def delete_kind_clusters() -> None:
    server.shell(
        name="Stop running kind clusters",
        commands="kind get clusters | xargs -I {} kind delete cluster --name {} || true",
    )

    result = server.shell(
        name="Get kind clusters (no cluster expected)",
        commands=[
            # f"kubectl cluster-info --context kind-{NAME}",
            "kind get clusters",
        ],
    )
    python.call(
        name="Show kind clusters (no cluster expected)",
        function=log_callback,
        result=result,
    )


def git_clone_karmada() -> None:
    files.directory(
        name=f"Create {GITS} directory",
        path=GITS,
    )
    SOURCE = "https://github.com/karmada-io/karmada.git"
    REPO = f"{GITS}/karmada"
    server.shell(
        name=f"Clone/pull {SOURCE}",
        commands=[
            f"[ -d {REPO} ] || git clone --depth 1 {SOURCE} {REPO}",
            f"""
                cd {REPO}
                git pull
            """,
        ],
    )


def install_karmada_clusters() -> None:
    INSTALLER_URL = (
        "https://raw.githubusercontent.com/karmada-io/"
        "karmada/master/hack/install-cli.sh"
    )
    files.file(
        name="Remove old kubectl-karmada CLI",
        path="/usr/local/bin/kubectl-karmada",
        present=False,
    )
    files.file(
        name="Remove old karmadactl CLI",
        path="/usr/local/bin/karmadactl",
        present=False,
    )

    server.shell(
        name="Install Karmada CLI",
        commands=[
            f"curl -s {INSTALLER_URL} | sudo bash -s kubectl-karmada",
        ],
        _get_pty=True,
    )

    result = server.shell(
        name="Get kubectl-karmada version",
        commands=["kubectl-karmada version"],
    )
    python.call(
        name="Show kubectl-karmada version",
        function=log_callback,
        result=result,
    )

    server.shell(
        name="Execute hack/local-up-karmada.sh (long)",
        commands=[
            f"cd {GITS}/karmada && ./hack/local-up-karmada.sh",
        ],
    )

    result = server.shell(
        name="Get kind clusters",
        commands=["kind get clusters"],
    )
    python.call(
        name="Show kind clusters",
        function=log_callback,
        result=result,
    )

    server.shell(
        name="Fix missing part",
        commands=[
            """\
export KUBECONFIG=/root/.kube/karmada.config
kubectl config use-context karmada-apiserver
kubectl apply -f - <<EOF
apiVersion: apiregistration.k8s.io/v1
kind: APIService
metadata:
    name: v1alpha1.cluster.karmada.io
spec:
    group: cluster.karmada.io
    version: v1alpha1
    versionPriority: 10
    insecureSkipTLSVerify: true
    groupPriorityMinimum: 2000
    service:
        name: karmada-aggregated-apiserver
        namespace: karmada-system
        port: 443
EOF
"""
        ],
        _get_pty=True,
    )

    result = server.shell(
        name="Get kubectl get clusters",
        commands=[
            """
            export KUBECONFIG=/root/.kube/karmada.config
            kubectl config use-context karmada-apiserver
            kubectl get clusters
            """
        ],
    )
    python.call(
        name="Show kubectl get clusters",
        function=log_callback,
        result=result,
    )

    result = server.shell(
        name="Get Karmada Control Plane Pods",
        commands=[
            (
                """
                export KUBECONFIG=/root/.kube/karmada.config
                kubectl --context karmada-host get pods -n karmada-system
                """
            )
        ],
    )
    python.call(
        name="Show Karmada Control Plane Pods",
        function=log_callback,
        result=result,
    )

    result = server.shell(
        name="Get Karmada member1 Pods",
        commands=[
            (
                """
                export KUBECONFIG=/root/.kube/members.config
                kubectl --context member1 get pods -A
                """
            )
        ],
    )
    python.call(
        name="Show Karmada member1 Pods",
        function=log_callback,
        result=result,
    )


main()
