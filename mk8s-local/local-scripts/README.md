# Install / test scripts for Karmada/MicroK8s on a single server

### System Architecture Overview

This setup creates a complete, self-contained Karmada "cluster of clusters" on a single server. It is designed for development, testing, and demonstration purposes. The architecture consists of two main layers:

1.  **The Host Control Plane:**
    *   **Technology:** A single-node **MicroK8s** cluster running directly on the host server.
    *   **Role:** Its primary job is to host the **Karmada control plane components** (like `karmada-apiserver`, `karmada-scheduler`, etc.). It also runs a local Docker container registry to ensure a fast and reliable installation, independent of public internet availability during setup.

2.  **The Member Clusters:**
    *   **Technology:** Three fully independent, single-node **MicroK8s** clusters (`member1`, `member2`, `member3`).
    *   **Isolation:** Each member cluster is encapsulated within its own **LXD container**. This provides strong process and network isolation, simulating a realistic multi-cluster environment where each cluster is a distinct entity.
    *   **Role:** These are the "worker" clusters that are managed by Karmada and are intended to run user applications (like the Nginx demo).

#### Networking Design

An important part of this setup is how it establishes communication between the isolated components:

*   **LXD Bridge (`lxdbr0`):** LXD creates a virtual network bridge on the host, giving each member cluster container a private IP address. The `0-prepare-server.py` script ensures the host's firewall (`iptables`) is configured to allow routing to and from this bridge.
*   **API Server Port Forwarding:** To allow the Karmada control plane to manage the member clusters, `1-create-clusters-on-lxd.py` uses an LXD `proxy` device. It forwards unique ports on the host machine (e.g., `16441`, `16442`, `16444`) directly to the internal API server port (`16443`) of each respective LXD container. The generated kubeconfig files for the member clusters are modified to point to these host ports (`https://127.0.0.1:16441`), making them seamlessly accessible from the host.
*   **Local Container Registry:** To avoid dependency on external image registries during installation, `2-setup-karmada.py` enables the MicroK8s registry addon, which runs on the host at `localhost:32000`. It then pulls all required Karmada and Kubernetes images, re-tags them to point to this local registry, and pushes them. The Karmada installation is then configured to pull all images from this local, reliable source.

---

### The Process So Far (Scripts 0, 1, and 2)

The `Makefile` executes the scripts in a precise order to build this environment from scratch. Here is the step-by-step process:

#### Phase 1: Environment Preparation (`0-prepare-server.py`)

This script acts as the foundational setup for the host server.

1.  **Prerequisite Installation:** It installs all necessary system-level dependencies: `make`, `fish`, Docker (`docker.io`), MicroK8s, LXD, and `kubectl`.
2.  **Karmada CLI Tools:** It downloads and runs the official `install-cli.sh` script to install `karmadactl` and the `kubectl-karmada` plugin.
3.  **Network Configuration:** It installs and initializes LXD, creating the `lxdbr0` network bridge. Critically, it then verifies and repairs the host's network settings, ensuring the `lxdbr0` interface is active and that the necessary `iptables` firewall rules exist to allow traffic to and from the LXD containers. This step is vital for connectivity.

#### Phase 2: Member Cluster Provisioning (`1-create-clusters-on-lxd.py`)

This script builds the three "worker" clusters.

1.  **LXD Profile Creation:** It creates a special LXD profile (`microk8s`) with the necessary privileges (`security.nesting`, `security.privileged`) to allow MicroK8s to run correctly inside a container.
2.  **Container Launch:** For each cluster (`member1`, `member2`, `member3`), it launches a new Ubuntu 22.04 LXD container using this profile.
3.  **MicroK8s Installation:** Inside each container, it installs MicroK8s and enables the `dns` and `hostpath-storage` addons.
4.  **Port Forwarding & Kubeconfig Generation:** This is a key step.
    *   It configures an LXD proxy device to forward a unique host port (e.g., `16441`) to the container's internal MicroK8s API server port (`16443`).
    *   It extracts the default kubeconfig from inside the container.
    *   It **modifies this kubeconfig**, changing the `server` address from `127.0.0.1:16443` to the host's forwarded port (e.g., `127.0.0.1:16441`).
    *   It saves this modified, ready-to-use kubeconfig to `/root/<cluster_name>.config`.
5.  **Health Check:** It immediately tests the new kubeconfig and port forward by running `kubectl get nodes` to ensure the cluster is accessible from the host.

#### Phase 3: Karmada Control Plane Deployment (`2-setup-karmada.py`)

With the member clusters ready, this script installs and configures Karmada itself.

1.  **Host Cluster Preparation:** It enables the required addons on the *host's* MicroK8s instance: `dns`, `hostpath-storage`, and, most importantly, `registry`. It then waits for the local registry to become fully available.
2.  **Image Pre-loading:** It pulls all required Karmada and Kubernetes container images from public registries (`docker.io`, `registry.k8s.io`), re-tags them with the `localhost:32000/` prefix, and pushes them into the local registry.
3.  **Karmada Initialization:** It runs `karmadactl init`, but with flags like `--etcd-image`, `--karmada-apiserver-image`, etc., all pointing to the images in the local registry. This makes the installation fast and resilient to internet issues.
4.  **Cluster Joining:** After the control plane is up, it iterates through the member clusters and uses the `karmadactl join` command, providing the unique kubeconfig file for each cluster. This registers the cluster with Karmada and deploys the `karmada-agent` into it.
5.  **Final Verification:** The script concludes by polling the Karmada API until all three member clusters report a `Ready` status, confirming the entire system is operational.

After these three scripts complete, you have a fully functional Karmada environment ready for testing and application deployment.
