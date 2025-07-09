# NEPHELE SMO Deployment

These `pyinfra` scripts are designed to automate the deployment of a complete development and demonstration environment for the Synergetic Meta-Orchestrator (SMO) and the H3NI project.

The scripts will provision a target server with a **`KinD`** Kubernetes cluster, deploy a **Karmada** control plane on top of it, and build and deploy the associated **"Brussels Demo"** application (and other demos in the future.)

## Prerequisites

### On your Local Machine:

* Python 3
* `uv` (install via `pip install uv` or other recommended methods)

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

Then, set an environment variable with the name of your server:

```bash
export SERVER_NAME=my-server
```

### Run the deployment

```bash
uv run make deploy-kind
```

[![asciicast](https://asciinema.org/a/7SGZVckjTUnB0DFDa903pQSPj.svg)](https://asciinema.org/a/7SGZVckjTUnB0DFDa903pQSPj)

### What it does

The `make deploy-kind` command automates the setup of a complete, local multi-cluster Kubernetes lab on a single server.

In short, the process does the following:

1.  **Prepares the Server:** Wipes any old configurations and installs necessary tools like Docker, Go, and a local container registry.
2.  **Deploys the Control Plane:** Creates a primary Kubernetes cluster using `kind` and installs **Karmada** on it to act as the central multi-cluster manager.
3.  **Adds Monitoring:** Installs a full **Prometheus** monitoring stack and the Metrics Server into the Karmada control plane.
4.  **Creates a Member Cluster:** Spins up a second, separate `kind` cluster that will be managed by Karmada.
5.  **Builds a Demo App:** Compiles and pushes a sample application's container images to the local registry, preparing them for deployment.

The end result is a two-cluster environment managed by Karmada, complete with monitoring and a ready-to-deploy application.


## Alternative instructions

The same, or similar, scripts can be used to deploy the testbed on other Kubernetes instances (like microk8s or minikube or k3s).

Here are some additional information:

### Step-by-Step Deployment

Execute the following `pyinfra` scripts in order. Replace `TARGET_HOST` with your server's IP address or hostname.

1.  **Setup Server and Install Core Dependencies**
    *   This script prepares the server by installing base packages, Go, `uv`, Docker, and the Docker registry. It also clones and builds the `hdarctl` utility.
    ```bash
    uv run pyinfra -y --user root TARGET_HOST 0-setup-server.py
    ```

2.  **Build and Push the Brussels Demo Images**
    *   This script clones the SMO source code, builds the three "Brussels Demo" Docker images, and pushes them to the local Docker registry started in the previous step.
    ```bash
    uv run pyinfra -y --user root TARGET_HOST 1-build-bxl-demo.py
    ```

3.  **Deploy `microk8s` and Karmada**
    *   This script installs `microk8s` via `snap`, configures it with Cilium as the CNI, and then deploys the Karmada control plane and CLI tools onto the `microk8s` cluster.
    ```bash
    uv run pyinfra -y --user root TARGET_HOST 2-deploy-karmada-on-mk8s.py
    ```

(Or just run `make deploy`).

## Post-Deployment: Accessing the Environment

After the scripts complete, your target server will be running a single-node `microk8s` cluster with Karmada managing it.

*   **SSH into the server:** `ssh root@TARGET_HOST`
*   **Interact with Kubernetes:** Use the `microk8s kubectl` command. A kubeconfig file is also generated at `/root/.kube/config`.
*   **Check Cluster Status:**
    ```bash
    # Check the status of the microk8s cluster
    microk8s status --wait-ready

    # List the nodes
    microk8s kubectl get nodes
    ```
*   **Check Karmada Status:**
    ```bash
    # Check that Karmada pods are running
    microk8s kubectl get pods -n karmada-system

    # Use the Karmada CLI to view registered clusters
    microk8s kubectl karmada get clusters
    ```


## Additional utility scripts

This repository contains additional scripts for convenience.

### `rebuild-server.py`

This is a helper script specifically for **Hetzner Cloud users**. It automates the process of rebuilding a server to a clean Ubuntu 22.04 image and removing the old SSH key from your local `known_hosts` file.

**Prerequisites:**
*   Python `hcloud` library (`pip install hcloud`).
*   A Hetzner Cloud API token set as an environment variable: `export HETZNER_TOKEN="your_token_here"`

**Usage:**
*   Update the `SERVER_NAME` and `IP_ADDRESS` variables in the script.
*   Run the script: `python3 rebuild-server.py`

### `inventory.py`

This is a standard `pyinfra` inventory file. You can populate it with your host details to avoid typing the IP address and user in every command.

**Example `inventory.py`:**
```python
# inventory.py
hosts = {
    'smo_server': {
        'ssh_host': '157.180.84.240',
        'ssh_user': 'root',
    }
}
```

**Usage with inventory:**
```bash
# Target the 'smo_server' host defined in the inventory
pyinfra --user root -y inventory.py 0-setup-server.py
# etc.
```

## Troubleshooting

To get more detailed output when running a `pyinfra` script, add verbose flags (`-v`, `-vv`, or `-vvv`) or the `--debug` flag for maximum detail.

```bash
# Example of a verbose run for debugging
pyinfra -y -vvv --user root TARGET_HOST 2-deploy-karmada-on-mk8s.py
```

## References

### Overview

- https://documentation.nephele-hdar.netmode.ece.ntua.gr/information-models/hdag.html

### On Karmada

Documentation:

- https://karmada.io/docs/installation/
- https://karmada.io/docs/installation/install-cli-tools#install-kubectl-karmada

### Installing Karmada on Kind (if needed)

- https://karmada.io/docs/installation/#install-karmada-in-kind-cluster

### SMO install & BXL demo

- https://gitlab.eclipse.org/eclipse-research-labs/nephele-project/smo/-/blob/main/README.md
- https://gitlab.eclipse.org/eclipse-research-labs/nephele-project/smo/-/blob/main/examples/brussels-demo/README.md

