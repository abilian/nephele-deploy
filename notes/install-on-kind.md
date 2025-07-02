## Install Karmada in Kind cluster

Cf. <https://karmada.io/docs/installation/#install-karmada-in-kind-cluster>

kind is a tool for running local Kubernetes clusters using Docker container "nodes". It was primarily designed for testing Kubernetes itself, not for production.

0) Install Kind

```bash
brew install kind
```

2) Install kubectl-karmada:

```
curl -s https://raw.githubusercontent.com/karmada-io/karmada/master/hack/install-cli.sh | sudo bash -s kubectl-karmada
```

1) Create a cluster named host by hack/create-cluster.sh:

(`hack` is from the karmada repository).

```
hack/create-cluster.sh host $HOME/.kube/host.config
```

3) Install Karmada v1.2.0 by command kubectl karmada init:

```
kubectl karmada init --crds https://github.com/karmada-io/karmada/releases/download/v1.2.0/crds.tar.gz --kubeconfig=$HOME/.kube/host.config -d ~/etc/karmada --karmada-pki ~/etc/karmada/pki
```

`-d ~/etc/karmada --karmada-pki ~/etc/karmada/pki` is needed because otherwise it wants to write on /etc/karmada and it's not possible.

Then:

```bash
cp ~/etc/karmada/karmada-apiserver.config ~/.kube/
```

(Needed because the SMO wants to look in `~/.kube`).


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
