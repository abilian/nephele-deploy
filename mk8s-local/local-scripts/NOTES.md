# Local scripts for a Karmada on Microk8 installation

## Overview

This collection of scripts provides a comprehensive, automated framework for deploying a complete Karmada multi-cluster environment on a single server, verifying its functionality, and tearing it down cleanly. The system uses MicroK8s for the Kubernetes clusters and LXD to containerize and isolate the member clusters, simulating a realistic multi-cluster topology.

Here is a high-level overview of each component's role in the process:

### **Phase 1: Environment Setup & Provisioning**

*   **`0-prepare-server.py`**: This initial script prepares the host server by installing all the necessary dependencies. It ensures that MicroK8s (for the host control plane), LXD (for creating containerized clusters), Docker, and the Karmada command-line tools (`karmadactl` and `kubectl-karmada`) are installed and ready.

*   **`2-create-clusters-on-lxd.py`**: This script provisions three independent Kubernetes clusters (`member1`, `member2`, `member3`) inside LXD containers. For each container, it installs MicroK8s, waits for it to be ready, and enables necessary addons. Crucially, it extracts a unique `kubeconfig` file for each member cluster, which is essential for remote management.

### **Phase 2: Karmada Deployment and Configuration**

*   **`4-setup-karmada-on-mk8s.py`**: This is the core installation script. It sets up the Karmada control plane on the host's MicroK8s instance. A key feature is its use of a local Docker registry on the host, where it pre-emptively pushes all required container images. This ensures a fast and reliable installation that is independent of external network failures. It then proceeds to:
    1.  Initialize the Karmada control plane using `karmadactl init`.
    2.  Join the three member clusters to the control plane by registering them and deploying the `karmada-agent` to each one.

### **Phase 3: Verification and Testing**

*   **`5-check-karmada.py`**: After deployment, this script runs a series of automated checks to validate the entire setup from end to end:
    *   **Control Plane Health**: It verifies that all Karmada components are running correctly in the host cluster.
    *   **Member Cluster Status**: It confirms that all member clusters have successfully registered and are in a `Ready` state.
    *   **E2E Functionality Test**: It deploys a sample Nginx application along with a `PropagationPolicy`. This policy dictates that the application should only be deployed to `member1` and `member2`, while excluding `member3`. The script then verifies that the application pods are running on the correct clusters and are correctly absent from the excluded one.

### **Phase 4: Cleanup**

*   **`6-tidy-up.py`**: This final script cleanly dismantles the entire environment. It stops and deletes the LXD containers, removes the generated `kubeconfig` files and the custom LXD profile, and disables the local registry on the host, returning the server to its initial state.


### Additional resources

*   **`NOTES.md` and `samples` directory**: These files provide supporting documentation and examples. `NOTES.md` offers manual commands for a human operator to perform debugging and verification. The `samples` directory contains manifest files for deploying applications like Nginx and a more complex `Guestbook` application (which uses Custom Resource Definitions), demonstrating how to use Karmada's `PropagationPolicy` and `OverridePolicy`.


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
