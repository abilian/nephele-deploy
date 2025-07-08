# Temporary Karmada installation scripts

- [install-on-kind.sh](install-on-kind.sh) installs Karmada and the rest of needed infra on Kind
- [deinstall-on-kind.sh](deinstall-on-kind.sh) clean up
- [install-prometheus.sh](install-prometheus.sh): supposed to install Prometheus (doesn't work, see below).
- [install-prometheus-crds.sh](install-prometheus-crds.sh): install Prometheus CRDS (as per `https://gitlab.eclipse.org/eclipse-research-labs/nephele-project/smo`, section "Prerequisites")

See [../notes/install-on-kind.md](../notes/install-on-kind.md) for additional notes.


## Notes on Prometheus

Install guide is:

<https://gitlab.eclipse.org/eclipse-research-labs/nephele-project/nephele-platform#kube-prometheus-stack>

But there is an issue:

- Bug: https://gitlab.eclipse.org/eclipse-research-labs/nephele-project/nephele-platform/-/issues/1

(Workaround: `helm repo add prometheus-community https://prometheus-community.github.io/helm-charts` doesn't work)

References:

- https://kubernetestraining.io/blog/deploying-the-kube-prometheus-stack-a-comprehensive-guide-to-kubernetes-monitoring
- https://artifacthub.io/packages/helm/prometheus-community/kube-prometheus-stack
- https://github.com/prometheus-community/helm-charts/tree/main/charts/kube-prometheus-stack

### Debug

```bash
helm show values prometheus-community/kube-prometheus-stack
```

### Solution / Workaround

Remove / comment out from `prom-values.yaml`:

```text
#additionalPrometheusRulesMap:
#   - name: test-rules
#     groups:
#       - name: smo-alerts
```

Then rerun:

```bash
❯ helm install prometheus --create-namespace -n monitoring \
           prometheus-community/kube-prometheus-stack --values prom-values.yaml
```

Then we get:

```text
NAME: prometheus
LAST DEPLOYED: Tue Jul  8 08:35:26 2025
NAMESPACE: monitoring
STATUS: deployed
REVISION: 1
NOTES:
kube-prometheus-stack has been installed. Check its status by running:
  kubectl --namespace monitoring get pods -l "release=prometheus"

Get Grafana 'admin' user password by running:

  kubectl --namespace monitoring get secrets prometheus-grafana -o jsonpath="{.data.admin-password}" | base64 -d ; echo

Access Grafana local instance:

  export POD_NAME=$(kubectl --namespace monitoring get pod -l "app.kubernetes.io/name=grafana,app.kubernetes.io/instance=prometheus" -oname)
  kubectl --namespace monitoring port-forward $POD_NAME 3000

Visit https://github.com/prometheus-operator/kube-prometheus for instructions on how to create & configure Alertmanager and Prometheus instances using the Operator.
```

```text
❯ kubectl --namespace monitoring get pods -l "release=prometheus"
NAME                                                   READY   STATUS    RESTARTS   AGE
prometheus-kube-prometheus-operator-779fdfbf6d-xx9nj   1/1     Running   0          2m22s
prometheus-kube-state-metrics-7955b7478-gk6pt          1/1     Running   0          2m22s
prometheus-prometheus-node-exporter-vs8jf              1/1     Running   0          2m22s
```
