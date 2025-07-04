# Note on installing the SMO on Kind (a "Kubernetes in Docker" flavor)

Kind is a tool for running local Kubernetes clusters using Docker container "nodes". It was primarily designed for testing Kubernetes itself, not for production.

Note that this not complete yet.

## First attempt

### Install kind

`brew install kind` on Linux or MacOS. (Homebrew must be installed first).

### Install Karmada in Kind cluster

Once kind is installed, follow:

Cf. <https://karmada.io/docs/installation/#install-karmada-in-kind-cluster>

1) Install kubectl-karmada:

```
curl -s https://raw.githubusercontent.com/karmada-io/karmada/master/hack/install-cli.sh | sudo bash -s kubectl-karmada
```

2) Create a cluster named host by hack/create-cluster.sh:

(`hack` is from the karmada repository).

```
hack/create-cluster.sh host $HOME/.kube/host.config
```

3) Install Karmada v1.2.0 by command kubectl karmada init:

```
kubectl karmada init --crds https://github.com/karmada-io/karmada/releases/download/v1.2.0/crds.tar.gz --kubeconfig=$HOME/.kube/host.config -d ~/etc/karmada --karmada-pki ~/etc/karmada/pki
```

`-d ~/etc/karmada --karmada-pki ~/etc/karmada/pki` is needed because otherwise it wants to write on /etc/karmada and it's not possible, or you have to be root, and there this opens another set of problems.

Then:

```bash
cp ~/etc/karmada/karmada-apiserver.config ~/.kube/
```

(Needed because the SMO wants this file to be in `~/.kube`).


4) Check installed components:

```
$ kubectl get pods -n karmada-system --kubeconfig=$HOME/.kube/host.config
NAME                                           READY   STATUS    RESTARTS   AGE
etcd-0                                         1/1     Running   0          2m55s
karmada-aggregated-apiserver-84b45bf9b-n5gnk   1/1     Running   0          109s
karmada-apiserver-6dc4cf6964-cz4jh             1/1     Running   0          2m40s
karmada-controller-manager-556cf896bc-79sxz    1/1     Running   0          2m3s
karmada-scheduler-7b9d8b5764-6n48j             1/1     Running   0          2m6s
karmada-webhook-7cf7986866-m75jw               1/1     Running   0          2m
kube-controller-manager-85c789dcfc-k89f8       1/1     Running   0          2m10s
```

```
$ kubectl get clusters --kubeconfig ~/etc/karmada/karmada-apiserver.config
NAME        VERSION   MODE   READY   AGE
kind-host   v1.31.2   Pull   True    118s
```

```text
❯ export KUBECONFIG="$HOME/.kube/host.config"

~
❯ kubectl config use-context host
Switched to context "host".

~
❯ kubectl config view
apiVersion: v1
clusters:
- cluster:
    certificate-authority-data: DATA+OMITTED
    server: https://192.168.117.2:6443
  name: kind-host
contexts:
- context:
    cluster: kind-host
    user: kind-host
  name: host
current-context: host
kind: Config
preferences: {}
users:
- name: kind-host
  user:
    client-certificate-data: DATA+OMITTED
    client-key-data: DATA+OMITTED
```


## 2nd attempt (should be automatable)

See [script](../bash-scripts/install-on-kind.sh)

Note: if not installing as root (for instance on a Mac), you would need instead:

```bash
mkdir etc
kubectl karmada init --crds https://github.com/karmada-io/karmada/releases/download/v1.2.0/crds.tar.gz --kubeconfig=$HOME/.kube/config -d ~/etc/karmada --karmada-pki ~/etc/karmada/pki
cp ~/etc/karmada/karmada-apiserver.config ~/.kube/
```

Then use

### Cleaning up and restarting from scratch

```bash
kubectl karmada deinit
kind delete cluster -n karmada-cluster
```
