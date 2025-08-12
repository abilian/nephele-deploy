# Karmada on MicroK8s/LXD: A Local Testbed

This project provides a fully automated framework for deploying a complete, multi-cluster [Karmada](https://karmada.io/) environment on a single server. It uses [MicroK8s](https://microk8s.io/) for the Kubernetes clusters and [LXD](https://linuxcontainers.org/lxd/) to create realistic, OS-level isolation for each member cluster.

The entire system is designed for development, testing, and demonstration of federated applications and can be provisioned and torn down with a single command.

### Key Features

*   **Fully Automated Setup**: Deploys a complete multi-cluster environment from a clean Ubuntu/Debian OS.
*   **Realistic Isolation**: Uses LXD to run each member cluster in its own system container, simulating separate machines.
*   **Demo Applications**: Includes scripts to deploy Nginx, a public Flask app, a custom-built Flask app, and a standalone Prometheus instance on each member cluster.
*   **Dynamic Cluster Management**: Provides `add-cluster.py` and `destroy-cluster.py` scripts to dynamically scale the federation.
*   **Resilience Testing**: Includes a `chaos-monkey.py` script to simulate random cluster failures.
*   **Comprehensive Verification**: A `8-verify-full-system.py` script validates the health and connectivity of every component.

### How to Run

#### The Easy Way (Automated via `test-server.py`)

This method will provision a new server on Hetzner Cloud, set it up, and run all the installation and demo scripts.

**Prerequisites:**
1.  Set the `HETZNER_TOKEN` environment variable.
2.  Set the `SERVER_NAME` environment variable to the desired name of your cloud server (e.g., `export SERVER_NAME=mk8s-testbed`).
3.  Ensure your local SSH key is configured to be used with new Hetzner servers.

**Execution:**
```bash
make test-e2e
```

#### The Manual Way (On any Ubuntu/Debian Server)

This method is for deploying on an existing server.

**Prerequisites:**
1.  An existing server running Ubuntu 22.04/24.04 or Debian.
2.  Root access to the server.
3.  Set the `SERVER_NAME` environment variable to the IP address or DNS name of your server.

**Execution:**
1.  Push the scripts from your local machine to the server:
    ```bash
    make push-local-scripts
    ```
2.  SSH into the server and run the scripts in sequence:
    ```bash
    ssh root@${SERVER_NAME}

    # On the server:
    cd /root/local-scripts
    
    # Run the installation and demo pipeline
    ./0-prepare-server.py
    ./1-create-clusters-on-lxd.py
    ./2-setup-karmada.py
    ./3-check-karmada.py
    ./4-nginx-demo.py
    ./5-flask-demo-1.py
    ./5-flask-demo-2.py
    ./6-install-prometheus.py
    
    # Run the final verification
    ./8-verify-full-system.py
    ```

### The Scripts: Execution Flow

The automation is composed of several scripts, each with a specific role:

*   **`0-prepare-server.py`**: **Host Setup.** Installs all system dependencies like MicroK8s, LXD, Docker, Helm, and the Karmada CLI tools. It also configures the host's firewall and network bridge.
*   **`1-create-clusters-on-lxd.py`**: **Member Cluster Provisioning.** Creates three LXD containers (`member1`, `member2`, `member3`), installs a full MicroK8s cluster in each one, and sets up LXD proxies for API server access.
*   **`2-setup-karmada.py`**: **Federation Setup.** Deploys the Karmada control plane onto the host MicroK8s cluster and joins the three member clusters to the federation.
*   **`3-check-karmada.py` / `4-nginx-demo.py`**: **Initial Demos.** Run basic health checks and deploy a simple Nginx application to verify propagation.
*   **`5-flask-demo-1.py` / `5-flask-demo-2.py`**: **Application Demos.** Deploy a Flask application using both a public image and a custom-built image (demonstrating the `build->save->push->import` workflow).
*   **`6-install-prometheus.py`**: **Monitoring Setup.** Deploys a standalone Prometheus instance into each member cluster and exposes its UI on the host.

### Additional Information

See the [OVERVIEW.md](./OVERVIEW.md) file for a deeper architectural breakdown, critical design patterns, and a troubleshooting guide.
