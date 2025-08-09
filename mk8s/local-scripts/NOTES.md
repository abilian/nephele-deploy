#

## Random notes

### Cleanup a karmada install

```bash
yes | kubectl karmada deinit
```

## Checking that this works

### Initial Setup: Point to the Karmada Control Plane

First and most importantly, configure your shell to talk to the Karmada control plane. All the following commands assume you have run this first:

```bash
export KUBECONFIG=~/.kube/karmada.config
```

---

### Level 1: Check the Health of the Control Plane

This is the first and most crucial step. You need to ensure all the Karmada components are running correctly on your host MicroK8s cluster.

**Command:**
```bash
kubectl get pods -n karmada-system
```

**✅ Expected Output:**
You should see all pods in the `karmada-system` namespace in a `Running` state, with all containers ready (e.g., `1/1`, `2/2`).

```
NAME                                               READY   STATUS    RESTARTS   AGE
etcd-0                                             1/1     Running   0          5m
karmada-aggregated-apiserver-7b7d7f6c6f-abcde      1/1     Running   0          4m
karmada-apiserver-6c6b8c9d9d-fghij                 1/1     Running   0          4m
karmada-controller-manager-5f5f6f7f7f-klmno        1/1     Running   0          4m
karmada-kube-controller-manager-5d5d6d7d7d-pqrst   1/1     Running   0          4m
karmada-scheduler-8b8b9b8b8b-uvwxy                 1/1     Running   0          4m
karmada-webhook-6f6f7f8f8f-yz123                   1/1     Running   0          4m
```

❗ **What to do if it fails:**
*   **`Pending` Status:** The host cluster might not have enough CPU/memory. Check `kubectl describe pod <pod-name> -n karmada-system` for scheduling errors.
*   **`ImagePullBackOff` or `ErrImagePull`:** There was a problem pulling the container image from the internet. Check your network connection.
*   **`CrashLoopBackOff`:** The container is starting and then crashing. This indicates a configuration error. Check the logs with `kubectl logs <pod-name> -n karmada-system`.

---

### Level 2: Check the Status of Member Clusters

Next, ask Karmada if it can see and communicate with the member clusters you joined.

**Command:**
```bash
kubectl get clusters
```

**✅ Expected Output:**
You should see all your member clusters listed with a `READY` status of `True`.

```
NAME      VERSION   MODE   READY   AGE
member1   v1.28.3   Push   True    3m
member2   v1.28.3   Push   True    3m
member3   v1.28.3   Push   True    3m
```

❗ **What to do if it fails:**
*   If `READY` is `False`, it means the `karmada-agent` running in that member cluster cannot communicate with the control plane.
*   **To debug**, check the logs of the `karmada-agent` pod *inside the member cluster*. For example, to debug `member1`:
    ```bash
    # Note: Use the member cluster's config file here
    kubectl --kubeconfig ./member1.config get pods -n karmada-system
    # Find the karmada-agent pod name, then:
    kubectl --kubeconfig ./member1.config logs -n karmada-system <agent-pod-name>
    ```

---

### Level 3: Perform an End-to-End Functionality Test (Most Definitive)

The best way to confirm everything is working is to deploy an application and let Karmada distribute it to your member clusters.

Here’s how to deploy an Nginx server to `member1` and `member2`, but not `member3`.

#### Step A: Create the Application Deployment

Create a file named `nginx-deployment.yaml`. This is a standard Kubernetes Deployment.

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: nginx-deployment
  labels:
    app: nginx
spec:
  replicas: 2
  selector:
    matchLabels:
      app: nginx
  template:
    metadata:
      labels:
        app: nginx
    spec:
      containers:
      - name: nginx
        image: nginx:1.21.6
        ports:
        - containerPort: 80
```

#### Step B: Create the Karmada Propagation Policy

Create a file named `nginx-policy.yaml`. This special Karmada resource tells the control plane how to distribute the Nginx deployment.

```yaml
apiVersion: policy.karmada.io/v1alpha1
kind: PropagationPolicy
metadata:
  name: nginx-propagation
spec:
  resourceSelectors:
    - apiVersion: apps/v1
      kind: Deployment
      name: nginx-deployment
  placement:
    clusterAffinity:
      clusterNames:
        - member1
        - member2
```

#### Step C: Apply the Files

Apply both files to the Karmada control plane.

```bash
kubectl apply -f nginx-deployment.yaml
kubectl apply -f nginx-policy.yaml
```

#### Step D: Verify the Deployment

Now, check if Karmada did its job.

1.  **Check from the Karmada Control Plane:**
    *   Use the `kubectl karmada` plugin to see the aggregated status of your deployment.
      ```bash
      kubectl karmada get deployment
      ```
      **✅ Expected Output:**
      ```
      NAME               CLUSTER   READY   UP-TO-DATE   AVAILABLE   AGE
      nginx-deployment                                   2/2         60s
      ```
    *   Check the `work` status, which shows what Karmada has distributed to each cluster.
      ```bash
      kubectl get work -A
      ```
      **✅ Expected Output:** You should see a `work` object for `nginx-deployment` in the namespaces for `member1` and `member2`, and they should report `Applied`.
      ```
      NAMESPACE            NAME                                 AGE
      karmada-es-member1   nginx-deployment-5d7f7d7d7d          90s
      karmada-es-member2   nginx-deployment-5d7f7d7d7d          90s
      ```

2.  **Check Directly on the Member Clusters:**
    *   Verify that `nginx` pods are running on `member1` and `member2`.
      ```bash
      kubectl --kubeconfig ./member1.config get pods
      kubectl --kubeconfig ./member2.config get pods
      ```
      **✅ Expected Output (for both commands):** You should see two running `nginx` pods.

    *   Verify that **no** `nginx` pods are running on `member3` (since it wasn't in our policy).
      ```bash
      kubectl --kubeconfig ./member3.config get pods
      ```
      **✅ Expected Output:** `No resources found in default namespace.`

If all these checks pass, your Karmada installation is fully functional.
