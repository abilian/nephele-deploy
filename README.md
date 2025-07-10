# NEPHELE SMO Deployment

These `pyinfra` scripts are designed to automate the deployment of a complete development and demonstration environment for the Synergetic Meta-Orchestrator (SMO) and related projects.

The main script (`make deploy-kind`) will provision a target server with a **`KinD`** (Kubernetes in Docker) based testbed. This includes a **Karmada** control plane to manage multiple clusters, a separate "member" cluster for workloads, a full monitoring stack, and the **"Brussels Demo"** application.

## Prerequisites

### On your Local Machine:

*   Python 3
*   `uv` (install via `pip install uv` or other recommended methods)

### On the Target Server:

*   An **Ubuntu or Debian** server (the scripts use `apt`).
*   SSH access with `root` privileges. All scripts are designed to be run as the `root` user.

## Deployment Instructions - Deploying the H3NI testbed on KinD

### Initial Setup

First, clone this repository and install the required Python dependencies on your local machine:

```bash
git clone <your-repo-url>
cd <repo-directory>
uv sync
```

Then, set an environment variable with the name or IP address of your target server. This should match the host defined in `kind-scripts/inventory.py`.

```bash
export SERVER_NAME=my-server
```

### Run the Deployment

Execute the all-in-one command to deploy the entire environment:

```bash
uv run make deploy-kind
```

Here's a recording of a successful deployment:

[![asciicast](https://asciinema.org/a/DRWEc8j3pNaJpfq6GO8AOoRKS.svg)](https://asciinema.org/a/DRWEc8j3pNaJpfq6GO8AOoRKS)


### What Happens During Deployment?

The `make deploy-kind` command automates the setup of a complete, local multi-cluster Kubernetes lab on a single server. It executes a series of (declarative and idempotent) scripts in a specific order to build the environment from the ground up.

Process does the following:

1.  **Prepares the Server (`0-setup-server.py`):** Wipes any old configurations and installs necessary tools like Docker, Go, and `uv`. It also starts a local container registry on port 5000.
2.  **Deploys the Control Plane (`1-deploy-karmada-on-kind.py`):** Creates a primary Kubernetes cluster using `kind` (named `karmada-cluster`) and installs **Karmada** on it to act as the central multi-cluster manager.
3.  **Adds Monitoring (`2-install-prometheus-on-kind.py` & `3-install-prometheus-crds-on-kind.py`):** Installs a full **Prometheus** monitoring stack into the `karmada-cluster` and applies the necessary Custom Resource Definitions (CRDs) so Karmada can manage monitoring resources across member clusters.
4.  **Adds Metrics Server (`4-install-metrics-server-kind.py`):** Deploys the Kubernetes Metrics Server to the Karmada control plane.
5.  **Creates a Member Cluster (`6-install-some-kind-cluster.py`):** Spins up a second, separate `kind` cluster (named `bxl-cluster`) that will be managed by Karmada.
6.  **Builds the Demo App (`7-build-bxl-demo-local-kind.py`):** Clones the SMO project, compiles the "Brussels Demo" application, and pushes its container images to the local registry, preparing them for deployment.

The end result is a two-cluster environment managed by Karmada, complete with monitoring and a ready-to-deploy application.

## Post-Deployment: Accessing the Environment

After the scripts complete, your target server will be running two `KinD` clusters.

*   **SSH into the server:** `ssh root@TARGET_HOST`

*   **Check `KinD` Cluster Status:**
    ```bash
    # List the running kind clusters
    kind get clusters
    # Expected output:
    # bxl-cluster
    # karmada-cluster
    ```

*   **Check the Local Docker Registry:**
    ```bash
    # See the images built for the Brussels Demo
    curl -s http://localhost:5000/v2/_catalog | python3 -m json.tool
    # Expected output:
    # {
    #     "repositories": [
    #         "custom-vo",
    #         "image-detection",
    #         "noise-reduction"
    #     ]
    # }
    ```

*   **Interact with the Karmada Control Plane:**
    The main kubeconfig for Karmada is located at `/root/.kube/karmada-apiserver.config`.
    ```bash
    # Set the KUBECONFIG environment variable for easier access
    export KUBECONFIG=/root/.kube/karmada-apiserver.config

    # Check that Karmada pods are running
    kubectl get pods -n karmada-system

    # Use the Karmada CLI to see that no clusters are registered yet
    kubectl karmada get clusters
    # Expected output:
    # No resources found
    ```

*   **Interact with the Member (`bxl-cluster`) and Host (`karmada-cluster`) Clusters:**
    You can use the default kubeconfig (`/root/.kube/config`) with different contexts.
    ```bash
    # See available contexts
    kubectl config get-contexts

    # Switch to the bxl-cluster context
    kubectl config use-context kind-bxl-cluster

    # List the nodes of the member cluster
    kubectl get nodes
    ```

*   **Next Steps: Register the Member Cluster**
    The deployment scripts set up the clusters but do not yet register the member cluster with the Karmada control plane. To do this, run the `karmada-agent`:
    ```bash
    # First, get the join token from the control plane
    export KUBECONFIG=/root/.kube/karmada-apiserver.config
    kubectl karmada token create bxl-cluster --print-register-command

    # This will output a `kubectl karmada register...` command.
    # Copy and run that command to register the cluster.

    # After running the command, verify the cluster is registered:
    kubectl karmada get clusters
    # Expected output:
    # NAME          VERSION   MODE   READY   AGE
    # bxl-cluster   v1.29.2   Push   True    1m
    ```

## Additional utility scripts

### `rebuild-server.py`

This is a helper script specifically for **Hetzner Cloud users**. It automates the process of rebuilding a server to a clean Ubuntu 22.04 image and removing the old SSH key from your local `known_hosts` file.

**Prerequisites:**

*   Python `hcloud` library (`pip install hcloud`).
*   A Hetzner Cloud API token set as an environment variable: `export HETZNER_TOKEN="your_token_here"`

**Usage:**

*   Update the `SERVER_NAME` and `IP_ADDRESS` variables in the script.
*   Run the script: `python3 rebuild-server.py`

### `inventory.py`

This is a standard `pyinfra` inventory file. You can populate it with your host details to avoid typing the IP address and user in every command. By default, it uses the `SERVER_NAME` environment variable or falls back to "nephele".

## Troubleshooting

To get more detailed output when running a `pyinfra` script, add verbose flags (`-v`, `-vv`, or `-vvv`) or the `--debug` flag for maximum detail.

```bash
# Example of a verbose run for debugging
uv run pyinfra -y -vvv --user root TARGET_HOST 0-setup-server.py
```

## References

### Overview

-   https://documentation.nephele-hdar.netmode.ece.ntua.gr/information-models/hdag.html

### On Karmada

Documentation:

-   https://karmada.io/docs/installation/
-   https://karmada.io/docs/installation/install-cli-tools#install-kubectl-karmada
-   https://karmada.io/docs/installation/#install-karmada-in-kind-cluster

### SMO install & BXL demo

-   https://gitlab.eclipse.org/eclipse-research-labs/nephele-project/smo/-/blob/main/README.md
-   https://gitlab.eclipse.org/eclipse-research-labs/nephele-project/smo/-/blob/main/examples/brussels-demo/README.md
