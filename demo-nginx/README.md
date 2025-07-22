# Test of KinD cluster

These scripts are intended to demonstrate the basic setup of a KinD cluster. They should display the initial Nginx homepage at the end of the sequence.

Scripts require `pyinfra` on the local host.

Remote server requirements:

- **Ubuntu** or **Debian** server.

- SSH access with `root` privileges. All scripts are designed to be run as the `root` user.


## Usage

Configure `inventory.py` or set an environment variable with the name or IP address of target server. This should match the host defined in `kind-scripts/inventory.py`.

```bash
export SERVER_NAME=my-server
```

## Run the Deployment

Execute the all-in-one command to deploy the entire environment:

```bash
make
```

## Result

```
--> Starting operation: Show all kubernetes pods
    ------------------------------------------------------------
    NAMESPACE            NAME                                                     READY   STATUS              RESTARTS   AGE
default              nginx-deployment-96b9d695-gsrx9                          0/1     ContainerCreating   0          12s
default              nginx-deployment-96b9d695-tplbw                          1/1     Running             0          12s
karmada-system       etcd-0                                                   1/1     Running             0          2m5s
karmada-system       karmada-aggregated-apiserver-6dc946d45f-9wkgt            1/1     Running             0          82s
karmada-system       karmada-apiserver-64fbcf4597-qcq5r                       1/1     Running             0          118s
karmada-system       karmada-controller-manager-6ff5b9f848-fnxcj              1/1     Running             0          58s
karmada-system       karmada-scheduler-74bcfc9567-cq9tx                       1/1     Running             0          65s
karmada-system       karmada-webhook-577d7d65bf-8vfvj                         1/1     Running             0          50s
karmada-system       kube-controller-manager-5bc7695896-5k9s7                 1/1     Running             0          69s
kube-system          coredns-674b8bbfcf-6xrl5                                 1/1     Running             0          2m49s
kube-system          coredns-674b8bbfcf-wqvhw                                 1/1     Running             0          2m49s
kube-system          etcd-host-control-plane                                  1/1     Running             0          2m56s
kube-system          kindnet-cgdsw                                            1/1     Running             0          2m45s
kube-system          kindnet-nhhqs                                            1/1     Running             0          2m50s
kube-system          kindnet-nk94l                                            1/1     Running             0          2m46s
kube-system          kube-apiserver-host-control-plane                        1/1     Running             0          2m55s
kube-system          kube-controller-manager-host-control-plane               1/1     Running             0          2m55s
kube-system          kube-proxy-dhdz7                                         1/1     Running             0          2m45s
kube-system          kube-proxy-gc4js                                         1/1     Running             0          2m46s
kube-system          kube-proxy-vzmx8                                         1/1     Running             0          2m50s
kube-system          kube-scheduler-host-control-plane                        1/1     Running             0          2m55s
kube-system          metrics-server-df8fbb54b-xcxsl                           0/1     Running             0          15s
local-path-storage   local-path-provisioner-7dc846544d-wbs9l                  1/1     Running             0          2m49s
monitoring           alertmanager-prometheus-kube-prometheus-alertmanager-0   0/2     PodInitializing     0          15s
monitoring           prometheus-grafana-65cfd7744f-ldxqp                      2/3     Running             0          22s
monitoring           prometheus-kube-prometheus-operator-68bcd76694-mm7jm     1/1     Running             0          22s
monitoring           prometheus-kube-state-metrics-7f5f75c85d-vpvbw           1/1     Running             0          22s
monitoring           prometheus-prometheus-kube-prometheus-prometheus-0       0/2     PodInitializing     0          14s
monitoring           prometheus-prometheus-node-exporter-8gj7d                1/1     Running             0          22s
monitoring           prometheus-prometheus-node-exporter-hbkq9                1/1     Running             0          22s
monitoring           prometheus-prometheus-node-exporter-z87vm                1/1     Running             0          22s
    ------------------------------------------------------------
    [nephele-jd] Success

--> Starting operation: Find docker IP for nginx
    [nephele-jd] Success

--> Starting operation: Show nginx docker IP
    ------------------------------------------------------------
    use the port on this IP: 172.18.0.2:31767
  % Total    % Received % Xferd  Average Speed   Time    Time     Time  Current
                                 Dload  Upload   Total   Spent    Left  Speed
100   615  100   615    0     0   145k      0 --:--:-- --:--:-- --:--:--  150k
<!DOCTYPE html>
<html>
<head>
<title>Welcome to nginx!</title>
<style>
    ------------------------------------------------------------
```
