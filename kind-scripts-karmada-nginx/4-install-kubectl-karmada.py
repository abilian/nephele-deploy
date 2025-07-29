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
# member2   v1.31.2   Push   True    58m
member3   v1.31.2   Pull   True    58m



"""

from pyinfra import host
from pyinfra.facts.files import File
from pyinfra.operations import apt, files, python, server, snap, systemd
import io
from common import log_callback
from constants import GITS

NO_MEMBER2_FILE = "/root/no_member2.patch"
NO_MEMBER2 = r"""\
diff --git a/hack/local-up-karmada.sh b/hack/local-up-karmada.sh
index a18ea97c7..e69229ba1 100755
--- a/hack/local-up-karmada.sh
+++ b/hack/local-up-karmada.sh
@@ -54,7 +54,7 @@ export HOST_CLUSTER_NAME=${HOST_CLUSTER_NAME:-"karmada-host"}
 export KARMADA_APISERVER_CLUSTER_NAME=${KARMADA_APISERVER_CLUSTER_NAME:-"karmada-apiserver"}
 export MEMBER_CLUSTER_KUBECONFIG=${MEMBER_CLUSTER_KUBECONFIG:-"${KUBECONFIG_PATH}/members.config"}
 export MEMBER_CLUSTER_1_NAME=${MEMBER_CLUSTER_1_NAME:-"member1"}
-export MEMBER_CLUSTER_2_NAME=${MEMBER_CLUSTER_2_NAME:-"member2"}
+# export MEMBER_CLUSTER_2_NAME=${MEMBER_CLUSTER_2_NAME:-"member2"}
 export PULL_MODE_CLUSTER_NAME=${PULL_MODE_CLUSTER_NAME:-"member3"}
 export HOST_IPADDRESS=${1:-}

@@ -70,20 +70,20 @@ GOPATH=$(go env GOPATH | awk -F ':' '{print $1}')
 KARMADACTL_BIN="${GOPATH}/bin/karmadactl"
 ${KARMADACTL_BIN} join --karmada-context="${KARMADA_APISERVER_CLUSTER_NAME}" ${MEMBER_CLUSTER_1_NAME} --cluster-kubeconfig="${MEMBER_CLUSTER_KUBECONFIG}" --cluster-context="${MEMBER_CLUSTER_1_NAME}"
 "${REPO_ROOT}"/hack/deploy-scheduler-estimator.sh "${MAIN_KUBECONFIG}" "${HOST_CLUSTER_NAME}" "${MEMBER_CLUSTER_KUBECONFIG}" "${MEMBER_CLUSTER_1_NAME}"
-${KARMADACTL_BIN} join --karmada-context="${KARMADA_APISERVER_CLUSTER_NAME}" ${MEMBER_CLUSTER_2_NAME} --cluster-kubeconfig="${MEMBER_CLUSTER_KUBECONFIG}" --cluster-context="${MEMBER_CLUSTER_2_NAME}"
-"${REPO_ROOT}"/hack/deploy-scheduler-estimator.sh "${MAIN_KUBECONFIG}" "${HOST_CLUSTER_NAME}" "${MEMBER_CLUSTER_KUBECONFIG}" "${MEMBER_CLUSTER_2_NAME}"
+# ${KARMADACTL_BIN} join --karmada-context="${KARMADA_APISERVER_CLUSTER_NAME}" ${MEMBER_CLUSTER_2_NAME} --cluster-kubeconfig="${MEMBER_CLUSTER_KUBECONFIG}" --cluster-context="${MEMBER_CLUSTER_2_NAME}"
+# "${REPO_ROOT}"/hack/deploy-scheduler-estimator.sh "${MAIN_KUBECONFIG}" "${HOST_CLUSTER_NAME}" "${MEMBER_CLUSTER_KUBECONFIG}" "${MEMBER_CLUSTER_2_NAME}"

 # step4. register pull mode member clusters and install scheduler-estimator
 "${REPO_ROOT}"/hack/deploy-agent-and-estimator.sh "${MAIN_KUBECONFIG}" "${HOST_CLUSTER_NAME}" "${MAIN_KUBECONFIG}" "${KARMADA_APISERVER_CLUSTER_NAME}" "${MEMBER_CLUSTER_KUBECONFIG}" "${PULL_MODE_CLUSTER_NAME}"

 # step5. deploy metrics-server in member clusters
 "${REPO_ROOT}"/hack/deploy-k8s-metrics-server.sh "${MEMBER_CLUSTER_KUBECONFIG}" "${MEMBER_CLUSTER_1_NAME}"
-"${REPO_ROOT}"/hack/deploy-k8s-metrics-server.sh "${MEMBER_CLUSTER_KUBECONFIG}" "${MEMBER_CLUSTER_2_NAME}"
+# "${REPO_ROOT}"/hack/deploy-k8s-metrics-server.sh "${MEMBER_CLUSTER_KUBECONFIG}" "${MEMBER_CLUSTER_2_NAME}"
 "${REPO_ROOT}"/hack/deploy-k8s-metrics-server.sh "${MEMBER_CLUSTER_KUBECONFIG}" "${PULL_MODE_CLUSTER_NAME}"

 # step6. wait all of clusters member1, member2 and member3 status is ready
 util:wait_cluster_ready "${KARMADA_APISERVER_CLUSTER_NAME}" "${MEMBER_CLUSTER_1_NAME}"
-util:wait_cluster_ready "${KARMADA_APISERVER_CLUSTER_NAME}" "${MEMBER_CLUSTER_2_NAME}"
+# util:wait_cluster_ready "${KARMADA_APISERVER_CLUSTER_NAME}" "${MEMBER_CLUSTER_2_NAME}"
 util:wait_cluster_ready "${KARMADA_APISERVER_CLUSTER_NAME}" "${PULL_MODE_CLUSTER_NAME}"

 function print_success() {
@@ -94,7 +94,8 @@ function print_success() {
   echo "Please use 'kubectl config use-context ${HOST_CLUSTER_NAME}/${KARMADA_APISERVER_CLUSTER_NAME}' to switch the host and control plane cluster."
   echo -e "\nTo manage your member clusters, run:"
   echo -e "  export KUBECONFIG=${MEMBER_CLUSTER_KUBECONFIG}"
-  echo "Please use 'kubectl config use-context ${MEMBER_CLUSTER_1_NAME}/${MEMBER_CLUSTER_2_NAME}/${PULL_MODE_CLUSTER_NAME}' to switch to the different member cluster."
+  # echo "Please use 'kubectl config use-context ${MEMBER_CLUSTER_1_NAME}/${MEMBER_CLUSTER_2_NAME}/${PULL_MODE_CLUSTER_NAME}' to switch to the different member cluster."
+  echo "Please use 'kubectl config use-context ${MEMBER_CLUSTER_1_NAME}/${PULL_MODE_CLUSTER_NAME}' to switch to the different member cluster."
 }

 print_success
"""


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

    # files.put(
    #     name="Put no_member2 patch",
    #     src=io.StringIO(NO_MEMBER2),
    #     dest=NO_MEMBER2_FILE,
    # )

    # server.shell(
    #     name="Patch hack/local-up-karmada.sh to remove member2",
    #     commands=[
    #         f"cd {GITS}/karmada && git apply {NO_MEMBER2_FILE}",
    #     ],
    #     _shell_executable="/bin/bash",
    #     _get_pty=True,
    #     _ignore_errors=True,
    # )

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
