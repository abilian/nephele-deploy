
# Deployment scripts for the SMO project

These `pyinfra` scripts are designed to deploy the NEPHELE infrastructure components (like Karmada), the Synergetic Meta-Orchestrator (SMO), and associated demonstration applications (e.g., "Brussels Demo") onto a target server. They assume you have a working SSH connection to the target server.

Our current approach for local development and testing utilizes `kind` (Kubernetes in Docker) to create a multi-cluster Kubernetes environment managed by Karmada.

Other approaches are certainly possible, but were harder to set up for us.


## Using the `kind`-based Deployment (Recommended)

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


# Older Notes & Scripts (Potentially Obsolete or for Specific Use Cases)

(These note are kept for the record, will be removed once the report is written).

Deployment scripts:

-   `deploy-docker.py`
-   `deploy-brussels.py`
-   `deploy-mk8s.py`
-   `deploy-infra.py`

Utilities scripts:

- `deploy-clean-all.py`


## Script `deploy-docker.py`

Deploy Docker and Docker registry on a target host, from official images of docker.com.

Command:
```bash
pyinfra -y -vvv --user USER HOST deploy-docker.py
```

-   Target host (HOST) is expected to bee Ubuntu or Debian.

-   A pre existing account (USER) with `ssh` acces is required.

What the script does:

-   Check that the server is Ubuntu or Debian

-   Install som base packages (curl, gpg, ...)

-   Install `docker.com` key and source list of packages

-   Install packages: `docker-ce`, `docker-ce-cli`, `containerd.io`

-   add USER to the docker group (allowing use of docker commands without need of `sudo`)

-  Install and start the official `registry` container. The registry is in insecure mode (no access restriction) on port 5000 by default (configure this port with REGISTRY_PORT constant if needed).


Caveats:

-   if some previous installation of Ubuntu package for docker, it will be necessary to remove them (and their stored images). See commented lines around line 93: "dpkg --purge --force-all containerd docker.io runc"

## Script `deploy-brussels.py`

Deploy the SMO code base and build the `brussels` docker images. The images are then pushed on the local docker `registry`. You need to ensure an existing `docker` environment (ie. use `deploy-docker.py`).

Command:
```bash
pyinfra -y -vvv --user USER HOST deploy-brussels.py
```

-   Target host (HOST) is expected to bee Ubuntu or Debian.

-   A pre existing account (USER) with `ssh` acces is required.

What the script does:

-   Check that the server is Ubuntu or Debian

-   Install some base packages (curl, gpg, ...)

-   Install `uv` for the USER

-   Download and install with `uv` the SMO code source. By default the Nephele SMO version, see SMO and SMO_URL constants to use another source repository.

-   Download and install the `hdarctl` binary (this implies the use of a amd64 host).

-   Build and install the 3 `brussels` demo images, push them on the local docker registry. The registry port (5000 by default) can be changed, see REGISTRY_PORT constant.

Caveats:

-   The docker registry is accessed via LOCAL_IP constant, set by default to `127.0.0.1`. This value can be changed to any address.


## Script `deploy-mk8s.py`

Deploy a minimal `microk8s` environment on a Ubuntu like distribution and activate `helm` and `prometheus` on it. `microk8s` is installed through the `snap` package system that contains preconfigured services (including `helm` and `prometheus`).

Command:
```bash
pyinfra -y -vvv --user USER HOST deploy-mk8s.py
```

-   Target host (HOST) is expected to bee Ubuntu or Debian.

-   A pre existing account (USER) with `ssh` acces is required.

What the script does:

-   Check that the server is Ubuntu or Debian

-   Install some base packages (curl, gpg, ...)

-   Install the `snapd` package

-   Install the `microk8s` package, enable `prometheus` plugin (`helm` is already activated)

-   Dump the microk8s configuration in local file `~/.kube/config`. This config file can be used to configure later a `karmada` server.


Caveats:

-   `Prometheus` is annouced deprecated, however an equivalent tool is proposed.

## Utility script `deploy-clean-all.py`

Remove all services, packages, docker images.

WARNING: this may be dangerous.

Command:
```bash
pyinfra -y -vvv --user USER HOST deploy-clean-all.py
```

-   Target host (HOST) is expected to bee Ubuntu or Debian.

-   A pre existing account (USER) with `ssh` acces is required.

What the script does:

-   Check that the server is Ubuntu or Debian

-   Stop systemd services

-   Remove snap packages: micro8s, lxd

-   Erase all Docker content (images, containers, volumes)

-   Remove docker packages

## Script `deploy-infra.py`

Not finished yet. This is a work in progress and not ready for production use.

Deploy the full `Nephele` project tools. This script tries to follow the `Nephele` project guidelines.


It's main goal is to test an installation of the `karmada` meta ochestrator.


Background information on how to install the platform (manually): https://gitlab.eclipse.org/eclipse-research-labs/nephele-project/nephele-platform

See also https://pad.cloud.abilian.com/-JKefCz7S3abBQhSbv1AIg# for some notes on the available installation documentation from NEPHELE.


## How to Run

### 1. Install

Run `uv sync` then activate the virtual environment (typically `source .venv/bin/activate`).

### 2. Setup (optional)

Update `inventory.py` with the correct SSH user and host information. The script assumes you have SSH access to the target server(s).

You may also call `pyinfra` directly with the ip address or the hostname of the server you want to deploy to, as described below.

### 3. Run the Deployment Script

*   **If targeting a single host by IP directly (e.g., `157.180.84.240`) with user `admin`:**
    ```bash
    pyinfra 157.180.84.240 -y -v --user root deploy-infra.py
    ```
    In this case, `host.name` will be `157.180.84.240`, and `TARGET_IP_FOR_MAKEFILE` will use this.

*   **If using `inventory.py` (e.g., the `smo_server_alias` example from `inventory.py` comments):**
    First, ensure `inventory.py` has something like:
    ```python
    # inventory.py
    hosts = {
        'smo_server_alias': {
            'ssh_host': 'actual_connect_ip_or_dns',
            'ssh_user': 'your_admin_user_with_sudo',
            'public_ip': '157.180.84.240' # The IP for the Makefile
        }
    }
    ```
    Then run:
    ```bash
    pyinfra inventory.py smo_server_alias deploy.py
    ```
    Or to target all hosts in the inventory:
    ```bash
    pyinfra inventory.py deploy.py
    ```
    In this case, `host.data.get('public_ip', host.name)` will pick up `'157.180.84.240'`.

* **Debugging**: add "-vv", "-vvv" and/or "--debug" to the command line to get more verbose output. This is useful for debugging and understanding what the script is doing. See <https://docs.pyinfra.com/en/3.x/cli.html#additional-debug-info> for more details.
