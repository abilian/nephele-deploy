# NEPHELE SMO Deployment

These `pyinfra` scripts are designed to automate the deployment of a complete development and demonstration environment for the Synergetic Meta-Orchestrator (SMO) and the H3NI project.

The scripts will provision a target server with a **`microk8s`** Kubernetes cluster, deploy a **Karmada** control plane on top of it, and build and deploy the associated **"Brussels Demo"** application (and other demos in the future.)

## Prerequisites

### On your Local Machine:

* Python 3
* `uv` (install via `pip install uv` or other recommended methods)

### On the Target Server:
*   An **Ubuntu or Debian** server (the scripts use `apt`).
*   SSH access with `root` privileges. All scripts are designed to be run as the `root` user.

## Deployment Instructions

The deployment is a three-step process. Run these commands from your local machine after cloning the repository.

### Initial Setup

First, clone this repository and install the required Python dependencies on your local machine:

```bash
git clone <your-repo-url>
cd <repo-directory>
uv sync
```

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


## Utility Scripts

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

### On Karmada

Documentation:

- https://karmada.io/docs/installation/
- https://karmada.io/docs/installation/install-cli-tools#install-kubectl-karmada

### Installing Karmada on Kind (if needed)

- https://karmada.io/docs/installation/#install-karmada-in-kind-cluster

### SMO install & BXL demo

- https://gitlab.eclipse.org/eclipse-research-labs/nephele-project/smo/-/blob/main/README.md
- https://gitlab.eclipse.org/eclipse-research-labs/nephele-project/smo/-/blob/main/examples/brussels-demo/README.md


## Detailed Script Descriptions

Here is a breakdown of what each script accomplishes on the target server.

### `0-setup-server.py`

**Purpose:** To prepare a fresh server with all the foundational tools required for the subsequent steps.

This script performs the following actions:

1.  **System Update:** Runs `apt update` and `apt upgrade` to ensure the system is up-to-date.
2.  **Base Packages:** Installs essential utilities like `curl`, `wget`, `vim`, and `gnupg`.
3.  **Go Installation:** Adds a PPA (Personal Package Archive) to install a recent version of the Go programming language. (Probably not needed anymore).
4.  **`uv` Installation:** Downloads and installs the `uv` Python package manager into `/usr/bin/` for system-wide access.
5.  **Docker Engine Installation:**
    *   Adds Docker's official GPG key and `apt` repository.
    *   Installs `docker-ce`, `docker-ce-cli`, and `containerd.io`.
6.  **Docker Registry:** Starts a Docker `registry:latest` container, exposing it on port `5000`. This registry is used to store the application images built in the next step.
7.  **HDAR Control (`hdarctl`)**:
    *   Clones the `hdar` source code from its Git repository.
    *   Builds the `hdarctl` command-line tool from source using Go.
    *   Copies the compiled `hdarctl` binary to `/usr/bin/` to make it available in the system's `PATH`.

### `1-build-bxl-demo.py`

**Purpose:** To build the "Brussels Demo" application container images and make them available for deployment.

This script relies on the tools installed by `0-setup-server.py`. It performs the following actions:

1.  **Install Build Tools:** Installs `git` and `build-essential` packages required for cloning and building software.
2.  **Clone SMO Repository:** Clones the main Synergetic Meta-Orchestrator source code.
3.  **Setup Python Environment:** Uses `uv` to create a Python virtual environment and install the SMO project's dependencies from its `requirements.txt` file.
4.  **Configure Makefile:** Modifies the `Makefile` within the `examples/brussels-demo/` directory, replacing a placeholder IP with `127.0.0.1` to ensure it points to the local Docker registry.
5.  **Build & Push Images:** Executes `make build-images` and `make push-images` to:
    *   Build the three Docker images for the Brussels Demo.
    *   Push these newly built images to the local Docker registry running on port `5000`.
6.  **Verify Push:** Runs a `curl` command to check that the images are listed in the local registry's catalog, confirming a successful push.

### `2-deploy-karmada-on-mk8s.py`

**Purpose:** To create the Kubernetes cluster environment and deploy the Karmada meta-orchestrator on top of it.

This is the final deployment script and performs the following actions:

1.  **Install `microk8s`:** Installs `microk8s` and `helm` using the `snap` package manager.
2.  **Start `microk8s`:** Waits for the `microk8s` service to be fully initialized and ready.
3.  **Configure Networking (CNI):** Enables the `cilium` community add-on, which provides container networking for the cluster.
4.  **Generate Kubeconfig:** Creates a Kubernetes configuration file at `/root/.kube/config` to allow `kubectl` to connect to the `microk8s` cluster.
5.  **Install Karmada CLI:** Downloads and installs the `kubectl-karmada` command-line tool, which is necessary for managing the Karmada control plane.
6.  **Deploy Karmada:**
    *   Runs `microk8s kubectl karmada init` to deploy the Karmada control plane components into the `microk8s` cluster.
    *   Waits for all pods in the `karmada-system` namespace to be in a `Ready` state.



## Missing steps

The current scripts setup the base infrastructure (`microk8s`, `docker`, `karmada`). However, they still are missing several important steps related to configuring the integration between these components and deploying the SMO application itself.

### 1. Missing Infrastructure Components

The SMO has dependencies on cluster components that are not being installed.

*   **Submariner:** The scripts do not install or configure Submariner, which is used for multi-cluster networking. (Not sure it's needed for a demon on a single machine).

*   **Prometheus CRDs:** The README provides a list of `kubectl apply` commands to install the Prometheus Operator CRDs into the Karmada control plane. This is essential for the `ServiceMonitor` resources to function.

### 2. Missing Core Configuration (The "Glue")

The components installed are not configured to communicate with the insecure local registry, which means Kubernetes (`containerd`) will fail to pull any of the application images we build.

*   **Docker Daemon Configuration:** The scripts do not configure the Docker daemon to trust the insecure registry. We need to add `{"insecure-registries": ["<Host-IP>:5000"]}` to `/etc/docker/daemon.json` and restart Docker.
*   **Containerd (Kubernetes) Configuration:** This is a multi-step process detailed in the README that the scripts do not perform currently:
    1.  Modify `/etc/containerd/config.toml` to set the registry `config_path`.
    2.  Create the directory `/etc/containerd/certs.d/<Host-IP>:5000/`.
    3.  Create a `hosts.toml` file inside that directory to tell `containerd` how to handle the insecure registry.

### 3. Missing SMO Application Deployment & Configuration

The scripts build the demo images but **never actually deploy the SMO application itself**.

*   **Running `docker compose up`:** The primary deployment method for the SMO is `docker compose up`.
*   **SMO Configuration Files (`.env` files):** The SMO requires configuration via `config/flask.env` and `config/postgres.env`. The scripts do not create or manage these files. A key missing step is setting the `KARMADA_KUBECONFIG` variable in `flask.env` to point to the correct file (e.g., `/root/.kube/karmada-apiserver.config`).

### 4. Missing "Brussels Demo" Final Deployment Steps

We run the `make build-images` and `make push-images` parts of the demo, but the full example requires several more steps to deploy the application graph.

*   **`make change-ips`:** This target, which updates IPs in the Helm charts, is not being run.
*   **`make push-artifacts`:** This step, which packages and pushes the Helm charts as OCI artifacts to the local registry, is missing.
*   **Running `create-existing-artifact.sh`:** This is the final and most important step of the demo. It calls the SMO API to request the deployment of the application graph. This is not automated.

More details in the [TODO](./TODO.md)

---

The notes below are for other/older approaches, that weren't successful (so far), but may work eventually.


## Using the `kind`-based Deployment (NOT WORKING)

Our current approach for local development and testing utilizes `kind` (Kubernetes in Docker) to create a multi-cluster Kubernetes environment managed by Karmada.

Other approaches are certainly possible, but were harder to set up for us.

This section outlines the new, preferred method for setting up a development environment.

*   **Prerequisites:**
    *   A target server (Linux, preferably Ubuntu or Debian) where you have `root` SSH access (e.g., passwordless sudo for your user, or direct root login if configured and understood).
    *   Ensure `pyinfra` and its dependencies are installed in your local environment (typically via `uv sync` in the project directory).

*   **Deployment Sequence (Run from your local machine, targeting `YOUR_HOST` as `root`):**

    1.  **`pyinfra -y --user root YOUR_HOST deploy-root-docker.py`**
        *   **Purpose:** Installs Docker Engine and starts a local, insecure Docker registry container listening on port 5000.
        *   **Note:** `YOUR_HOST` is the IP address or hostname of your target server.

    2.  **`pyinfra -y --user root YOUR_BUILD_HOST deploy-root-brussels.py`**
        *   **Purpose:**
            *   Clones the SMO source code (defaulting to the main NEPHELE SMO repository).
            *   Installs `hdarctl`.
            *   Builds the "Brussels Demo" Docker images.
            *   Pushes these images to the local Docker registry (from step 1) on `YOUR_BUILD_HOST`.
        *   **Note:**
            *   `YOUR_BUILD_HOST` is typically the same as `YOUR_HOST`.
            *   If different, ensure the Docker registry on `YOUR_HOST` (if that's where Karmada will run) is accessible from `YOUR_BUILD_HOST`, or adjust image pushing/pulling strategies accordingly.

    3.  **`pyinfra -y --user root YOUR_HOST deploy-root-kind-k8s.py`**
        *   **Purpose:**
            *   Installs `kind` (Kubernetes in Docker), Go (a `kind` dependency), Helm, and Cilium (as the CNI).
            *   Uses `kind` to create multiple Kubernetes clusters within Docker containers (e.g., `karmada-host` for the control plane, and `member1`, `member2`, etc., for applications).
            *   Installs and configures the Karmada control plane on the `karmada-host` cluster.
            *   Registers the `member` clusters with the Karmada control plane.

* **Post-Deployment Interaction:**
    *   You will have a Karmada control plane and several member Kubernetes clusters running within Docker containers on `YOUR_HOST`.
    *   To interact with them (e.g., to deploy SMO, Hop3, or applications via Karmada):
        *   Use `kubectl` with the appropriate configuration context. The `deploy-root-kind-k8s.py` script should configure a `kubeconfig` file on `YOUR_HOST` (often at `~/.kube/config` for the root user, or a specific Karmada config file).
        *   Refer to Karmada and `kind` documentation for details on switching contexts (e.g., `kubectl config use-context <context-name>`) to target either the Karmada API server or individual member clusters.

* **Important Considerations:**
    *   The Karmada installation using `kind` can be resource-intensive on `YOUR_HOST` (CPU and RAM) and may take a significant amount of time to complete.
    *   Advanced configuration of Karmada resources (like `PropagationPolicy`, `ClusterPropagationPolicy`) via YAML for custom deployments is an area for further exploration beyond the default setup.

## What Changed in Our Approach (From `microk8s` to `kind`)

*   **Previous Method:** Initial attempts to set up the multi-cluster Kubernetes environment for Karmada and SMO utilized `microk8s`. This approach presented several challenges in achieving a consistently stable and easily reproducible setup suitable for rapid development iterations.
*   **New Approach: `kind` (Kubernetes in Docker)**
    *   **Rationale for Change:**
        *   **Developer-Focused:** `kind` is explicitly designed for creating local Kubernetes clusters for development and testing purposes.
        *   **Karmada Alignment:** Crucially, `kind` is the **default and recommended method used in Karmada's official installation scripts** and examples. This suggests better inherent compatibility and a more streamlined setup process for the Karmada control plane and its member clusters.
        *   **Reproducibility & Isolation:** Using Docker containers for clusters provides good isolation and improves the reproducibility of the environment.
    *   **Goal:** To rapidly establish a functional multi-cluster Karmada environment on a single server, enabling the team to focus more effectively on SMO and H3NI component development and integration.

## Next Steps

The immediate focus is on:

1.  Fully stabilizing the `kind`-based multi-cluster environment provisioned by the `pyinfra` scripts.
2.  Deploying the SMO (and Hop3 plugin) onto this `kind`/Karmada setup.
3.  Commencing testing and validation of the H3NI components (Hop3 plugin, placement algorithms, and scaling logic).
4.  Thoroughly documenting the challenges encountered with the previous `microk8s` approach for inclusion in project reports and as lessons learned.

