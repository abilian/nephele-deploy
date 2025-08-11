# System Architecture Overview

The system is a **"cluster of clusters."** It consists of a central **Host Cluster** that runs the Karmada control plane, and three independent **Member Clusters** that are managed by Karmada and are ready to run applications.

This entire architecture runs on a single physical (or virtual) server, using layers of containerization to achieve isolation.

### Key Subsystems and Components

Here is a breakdown of the major subsystems and how they interact:

#### 1. The Host Server
*   **Operating System:** Debian/Ubuntu Linux.
*   **Core Technologies:** `snapd` (for MicroK8s/LXD), `iptables` (for host firewalling), `Docker` (for image management).
*   **Role:** Provides the physical resources (CPU, RAM, network) for all other components. It runs the main "host" MicroK8s cluster directly.

#### 2. The Host Cluster (MicroK8s)
*   **Technology:** A single-node MicroK8s Kubernetes cluster.
*   **Networking:**
    *   Uses Calico for its internal pod network (typically in the `10.1.0.0/16` range).
    *   Exposes its own API server on the host at `127.0.0.1:16443`.
*   **Role:** This cluster's primary job is to provide a stable Kubernetes environment to run the Karmada control plane components. It does **not** run user applications. It is the "brain" of the operation.

#### 3. The Karmada Control Plane
*   **Location:** Deployed as a set of pods within the `karmada-system` namespace on the **Host Cluster**.
*   **Core Components:**
    *   `etcd`: The key-value store that acts as the database for the Karmada control plane, storing all policies and cluster information.
    *   `karmada-apiserver`: A standard `kube-apiserver` that serves the core Kubernetes APIs for Karmada.
    *   `karmada-aggregated-apiserver`: An extension API server that serves Karmada's custom resource types, like `PropagationPolicy` and `Cluster`. This is the component that makes Karmada's features available.
    *   `karmada-controller-manager`: The primary controller that watches for `PropagationPolicy` objects and creates `Work` manifests to distribute applications.
    *   `karmada-scheduler`: Decides which member clusters to place applications on, based on the `placement` rules in policies.
    *   `karmada-webhook`: An admission webhook that validates and mutates Karmada API objects.
*   **API Endpoint:** The Karmada API is accessible via the administrative kubeconfig at `/etc/karmada/karmada-apiserver.config`.

#### 4. The Member Clusters (`member1`, `member2`, `member3`)
*   **Technology:** Three fully independent, single-node MicroK8s clusters.
*   **Isolation:** Each member cluster runs inside its own **LXD container**. This provides complete process and network isolation from the host and from each other.
*   **Role:** These are the "worker" clusters. Their job is to run the actual applications (like Nginx) that are distributed by the Karmada control plane.
*   **Communication with Karmada:**
    *   Each member cluster runs a `karmada-agent` pod in its `karmada-system` namespace.
    *   The `karmada-agent` is responsible for communicating with the Karmada control plane, reporting the cluster's status, and applying the `Work` manifests that the control plane sends it.

---

### Network Architecture and Open Ports

This is the most critical part of the setup.

#### 1. LXD Bridge (`lxdbr0`)
*   **Purpose:** A virtual network switch created by LXD on the host.
*   **Host IP:** The host machine has an IP address on this bridge (e.g., `10.x.y.1`), allowing it to route traffic to the containers.
*   **Container IPs:** Each LXD container (`member1`, `member2`, `member3`) gets a private IP address on this bridge's subnet (e.g., `10.x.y.187`).

#### 2. Host Firewall (`iptables`)
*   The `0-prepare-server.py` script ensures three critical rules are in place:
    *   **`INPUT` rule:** Allows the host itself to initiate connections **to** the containers on the `lxdbr0` bridge.
    *   **`FORWARD` rules (in/out):** Allows traffic to be routed between the `lxdbr0` bridge and the host's main network interface (`eth0`), enabling containers to reach the internet.

#### 3. LXD Port Forwarding (The Key to Connectivity)
*   **Purpose:** This is the mechanism that bypasses the complex host firewall and makes the member clusters easily accessible.
*   **Open Ports on the Host:** The `1-create-clusters-on-lxd.py` script opens the following ports on the host machine's `localhost` (127.0.0.1) and all other interfaces (`0.0.0.0`):
    *   `TCP 16441` -> forwards to `member1`'s internal API server on port `16443`.
    *   `TCP 16442` -> forwards to `member2`'s internal API server on port `16443`.
    *   `TCP 16444` -> forwards to `member3`'s internal API server on port `16443`.
*   **How it's used:** The `member*.config` files are modified to point to these `localhost` ports. When `karmadactl` or `kubectl` uses these files, it connects to the host's forwarded port, and LXD handles the rest.

#### 4. Local Container Registry
*   **Purpose:** To provide a fast and reliable source for all Karmada and Kubernetes container images, avoiding reliance on the public internet during installation.
*   **Open Port on the Host:** The MicroK8s registry addon opens `TCP 32000` on the host's `localhost` (`127.0.0.1`).
*   **How it's used:** The `2-setup-karmada.py` script pulls images from the internet, re-tags them with the `localhost:32000/` prefix, and pushes them to this local registry. The `karmadactl init` command is then configured to pull all its images from this local source.

### Summary Diagram

```
+-----------------------------------------------------------------+
| HOST SERVER (e.g., IP: 157.180.84.240)                           |
| +-------------------------------------------------------------+ |
| | Host MicroK8s Cluster (Listens on 127.0.0.1:16443)          | |
| | +---------------------------------------------------------+ | |
| | | Namespace: karmada-system                             | | | |
| | | +-------------------+  +----------------------------+ | | | |
| | | | Karmada Control   |  | Karmada Aggregated         | | | | |
| | | | Plane Pods        |--| APIServer (provides        | | | | |
| | | | (Scheduler, etc.) |  | cluster.karmada.io API)    | | | | |
| | | +-------------------+  +----------------------------+ | | | |
| | +---------------------------------------------------------+ | |
| +-------------------------------------------------------------+ |
|                                                                 |
|     localhost:32000 (Local Docker Registry) <-------------------+--- Docker Push (from script)
|                                                                 |
| +-------------------------+ +-------------------------+ +-------------------------+
| | LXD Container: member1  | | LXD Container: member2  | | LXD Container: member3  |
| | IP: 10.x.y.A            | | IP: 10.x.y.B            | | IP: 10.x.y.C            |
| | +---------------------+ | | +---------------------+ | | +---------------------+ |
| | | MicroK8s            | | | | MicroK8s            | | | | MicroK8s            | |
| | | API @ 127.0.0.1:16443 | | | API @ 127.0.0.1:16443 | | | API @ 127.0.0.1:16443 | |
| | +--------+------------+ | | +--------+------------+ | | +--------+------------+ |
| |          ^              | |          ^              | |          ^              |
| +----------|--------------+ +----------|--------------+ +----------|--------------+
|            |                           |                           |
|     LXD Port Forwarding                |                           |
| localhost:16441                        |                           |
|                                localhost:16442                 localhost:16444
|                                                                    |
+--------------------------------------------------------------------+
```
