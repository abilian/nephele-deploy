# Notes

## How to set up this thing

1) Install docker, kubernetes, karmada...

-> `make deploy`

2) Start the SMO locally

For example, `flask run -p 8000` in the `no-docker` branch. Or better:

```bash
flask --debug run --reload -p 8000
```

(Or deploy with `docker-compose`.)

3) Start the registry:

`docker-compose up` in the `smo/registry` directory.

4) Start prometheus:

```bash
sh original-scripts/deploy-prometheus.sh
```

5) Start Grafana:

```bash
docker run -d -p 3000:3000 --name=grafana grafana/grafana-enterprise
```

## Notes on Karmada installation

1) run `sudo kubectl karmada init`

2) Change permissions on `/etc/karmada`

3) Create cluster

```text
Karmada is installed successfully.

Register Kubernetes cluster to Karmada control plane.

Register cluster with 'Push' mode

Step 1: Use "kubectl karmada join" command to register the cluster to Karmada control plane. --cluster-kubeconfig is kubeconfig of the member cluster.
(In karmada)~# MEMBER_CLUSTER_NAME=$(cat ~/.kube/config  | grep current-context | sed 's/: /\n/g'| sed '1d'| tr -d "\"'")
(In karmada)~# kubectl karmada --kubeconfig /etc/karmada/karmada-apiserver.config  join ${MEMBER_CLUSTER_NAME} --cluster-kubeconfig=$HOME/.kube/config

Step 2: Show members of karmada
(In karmada)~# kubectl --kubeconfig /etc/karmada/karmada-apiserver.config get clusters


Register cluster with 'Pull' mode

Step 1: Create bootstrap token and generate the 'kubectl karmada register' command which will be used later.
~# kubectl karmada token create --print-register-command --kubeconfig=/etc/karmada/karmada-apiserver.config
This command will generate a registration command similar to:

kubectl karmada register 172.18.0.5:5443 --token t8xfio.640u9gp9obc72v5d --discovery-token-ca-cert-hash sha256:9cfa542ff48f43793d1816b1dd0a78ad574e349d8f6e005e6e32e8ab528e4244

Step 2: Use the output from Step 1 to register the cluster to the Karmada control plane.
You need to specify the target member cluster by flag '--kubeconfig'
~# kubectl karmada register 172.18.0.5:5443 --token t8xfio.640u9gp9obc72v5d --discovery-token-ca-cert-hash sha256:9cfa542ff48f43793d1816b1dd0a78ad574e349d8f6e005e6e32e8ab528e4244 --kubeconfig=<path-to-member-cluster-kubeconfig>

Step 3: Show members of Karmada.
~# kubectl karmada --kubeconfig=/etc/karmada/karmada-apiserver.config get clusters

The kubectl karmada register command has several optional parameters for setting the properties of the member cluster. For more details, run:

~# kubectl karmada register --help

```


## Testing / debugging the SMO

```
Endpoint                    Methods  Rule
--------------------------  -------  ---------------------------------
cluster.get_clusters        GET      /clusters/
flasgger.<lambda>           GET      /apidocs/index.html
flasgger.apidocs            GET      /docs/
flasgger.oauth_redirect     GET      /oauth2-redirect.html
flasgger.smo-api-spec       GET      /smo-api-spec.json
flasgger.static             GET      /flasgger_static/<path:filename>
graph.alert                 POST     /alerts
graph.deploy                POST     /project/<project>/graphs
graph.get_all_graphs        GET      /project/<project>/graphs
graph.get_graph             GET      /graphs/<name>
graph.placement             GET      /graphs/<name>/placement
graph.remove                DELETE   /graphs/<name>
graph.start                 GET      /graphs/<name>/start
graph.stop                  GET      /graphs/<name>/stop
os_k8s.delete_os_k8s        DELETE   /os_k8s/cluster/<string:smo_id>
os_k8s.get_os_k8s           GET      /os_k8s/cluster/<string:smo_id>
os_k8s.get_os_k8s_clusters  GET      /os_k8s/clusters
os_k8s.post_os_k8s          POST     /os_k8s/clusters
os_k8s.scale_out            POST     /os_k8s/scale-out/<string:smo_id>
os_k8s.sync_nfvcl           POST     /os_k8s/sync/nfvcl_k8s
static                      GET      /static/<path:filename>
vim.delete_smo_vim          DELETE   /vims/smo_vims/<string:smo_id>
vim.get_nfvcl_vims          GET      /vims/sync/nfvcl_vims
vim.get_smo_vim             GET      /vims/smo_vims/<string:smo_id>
vim.get_smo_vims            GET      /vims/smo_vims
vim.post_smo_vim            POST     /vims/smo_vims
```
