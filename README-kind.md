# Testbed Scenarios for KinD

This document outlines the various automated deployment scenarios available within this repository, all of which use `pyinfra` to provision a testbed environment based on KinD (Kubernetes in Docker). Each scenario is self-contained within a `kind-scripts-*` directory and is designed to test a specific aspect of the SMO platform, from basic federation to advanced application demonstrations.

## 1. Foundational Testbed (`kind-scripts`)

This is deployment is designed to set up the full H3NI testbed environment as described in the main `README.md`. It creates the foundational infrastructure upon which most demonstrations are built.

*   **Goal:** To provision a complete, multi-cluster Kubernetes lab managed by Karmada, including a full observability stack and the necessary application artifacts for the Brussels Demo.
*   **Entrypoint:** `make deploy-kind`
*   **Key Components & Sequence:**
    1.  **Server Setup (`0-setup-server.py`):** Prepares the host by installing Docker, Go, `uv`, and other base dependencies. It also starts a local Docker container registry.
    2.  **Karmada Control Plane (`1-deploy-karmada-on-kind.py`):** Deploys a KinD cluster named `karmada-cluster` to serve as the federation host and installs the Karmada control plane components into it.
    3.  **Monitoring Stack (`2-`, `3-`, `4-*.py`):** Installs the `kube-prometheus-stack` via Helm into the host cluster and applies the necessary Custom Resource Definitions (CRDs) to the Karmada control plane, enabling federated monitoring. A Metrics Server is also deployed.
    4.  **Member Cluster (`6-install-some-kind-cluster.py`):** Deploys a second KinD cluster named `bxl-cluster` to act as a workload cluster that will be managed by Karmada.
    5.  **Demo Application Build (`7-build-bxl-demo-local-kind.py`):** Clones the original SMO project, builds the container images for the "Brussels Demo," and pushes them to the local Docker registry.

This scenario results in a ready-state testbed but does not deploy the final application, leaving that step for the specific demo scenarios.

## 2. Karmada Federation Test with Nginx (`kind-scripts-demo0` / `kind-scripts-karmada-nginx`)

This scenario is designed to verify the core multi-cluster scheduling capabilities of Karmada with a simple, well-known application. It uses the official Karmada setup scripts to create a multi-member cluster environment.

*   **Goal:** To demonstrate that a standard Kubernetes workload (Nginx) can be deployed to a member cluster via the Karmada control plane using a `PropagationPolicy`.
*   **Entrypoint:** `make deploy-demo0` (which executes `make deploy-karmada-nginx` from the `kind-scripts-demo0/Makefile`)
*   **Key Components & Sequence:**
    1.  **Full Karmada Environment (`4-install-kubectl-karmada.py`):** Deploys a complete Karmada setup using the official `local-up-karmada.sh` script. This creates a host cluster (`karmada-host`) and multiple member clusters (`member1`, `member2`, `member3`).
    2.  **Prometheus on Members (`5-install-prometheus-members.py`):** Installs a basic Prometheus instance on each member cluster to test federated observability where members push metrics to a central host.
    3.  **Nginx Deployment (`13-deploy-nginx.py`):**
        *   Creates a standard Nginx `Deployment` manifest.
        *   Creates a Karmada `PropagationPolicy` that targets the Nginx deployment and schedules it to run on `member1`.
        *   Applies both manifests to the Karmada control plane.
        *   Verifies that the Nginx pods are successfully running on the `member1` cluster and exposes the service for access.

This scenario provides a clean and simple validation of the entire federation and networking stack.

## 3. The "Brussels Demo" (`kind-scripts-demo-bxl` / `kind-scripts-demo1`)

This is an end-to-end demonstration, deploying the full "Brussels Demo" application (from the original SMO) onto the Karmada testbed. Two versions of this demo exist, showcasing the project's evolution.

*   **Goal:** To showcase the full capabilities of the SMO, including HDAG artifact management, service placement, and interaction with a federated monitoring stack.
*   **Entrypoint:** `make deploy-bxl` (for the original SMO) or `make deploy-demo1` (for the refactored SMO Monorepo).
*   **Key Components & Sequence:**
    1.  **Full Karmada & Prometheus Setup:** Scripts deploy a complete multi-cluster environment with a host, multiple members, and a federated Prometheus stack. A key step is `8-merge-kube-configs.py`, which consolidates all cluster credentials into a single `karmada-apiserver.config` file for the SMO to use.
    2.  **SMO Installation:**
        *   **Original SMO (`10-install-nephele-smo.py`):** Clones the original `nephele-project/smo` repository, applies patches for KinD compatibility, configures it, and starts it via `docker-compose`.
        *   **SMO Monorepo (`0-2-install-smo-cli-monorepo.py`):** Clones the `smo-monorepo`, builds the `smo-cli`, and configures it.
    3.  **Brussels Demo Deployment (`12-install-bxl-demo.py` or `13-demo-bxl.py`):** These scripts automate the final steps from the Brussels Demo `README`:
        *   It builds and pushes the demo's container images.
        *   It packages the Helm charts and HDAG descriptor into OCI artifacts using `hdarctl`.
        *   It pushes these artifacts to the local registry.
        *   Finally, it calls the running SMO's REST API (or `smo-cli`) to deploy the application graph.

This scenario validates the entire toolchain and serves as the primary demonstration of the project's orchestration capabilities, with `demo1` representing the newer, CLI-driven approach.

## 4. GPU Offloading Demo (`kind-scripts-demo2`)

This scenario is specifically designed to test the SMO's resource-aware placement capabilities, focusing on workloads that require specialized hardware like GPUs.

*   **Goal:** To demonstrate that the SMO's placement algorithm can correctly identify and deploy a service to a cluster with GPU capabilities while placing non-GPU services on standard clusters.
*   **Entrypoint:** `make deploy-demo2`
*   **Key Components & Sequence:**
    1.  **Testbed & SMO Monorepo Setup:** The initial scripts set up the standard Karmada and Prometheus environment and install the `smo-cli` from the `smo-monorepo`.
    2.  **GPU Demo Deployment (`14-demo-gpu.py`):** This script uses the `h3ni-demos/2-gpu-offloading-demo` application. It builds and packages an application graph containing two services:
        *   `ml-inference`: An application that explicitly requires a GPU in its HDAG descriptor.
        *   `web-frontend`: A standard web application with no special hardware requirements.
    3.  It then uses `smo-cli graph deploy` to submit the graph to the SMO. The validation consists of using `smo-cli graph describe` to confirm that the `ml-inference` service was placed on a (simulated) GPU-enabled cluster and the `web-frontend` on another.

## 5. Autoscaling Demo (`kind-scripts-demo3`)

This scenario showcases the dynamic, metrics-driven autoscaling feature that has been integrated into the SMO.

*   **Goal:** To demonstrate that the SMO can automatically scale a deployed service up and down based on real-time request rates gathered from Prometheus.
*   **Entrypoint:** `make deploy-demo3`
*   **Key Components & Sequence:**
    1.  **Testbed & SMO Monorepo Setup:** The environment is prepared with Karmada, Prometheus, and the `smo-cli` (checked out from the `scaling` branch).
    2.  **Autoscaling Demo Deployment (`15-demo-autoscaling.py`):** This script uses the `h3ni-demos/3-autoscaling-demo` application. It deploys an initial application graph.
    3.  **Triggering the Scaler:** After deployment, the scenario uses the `smo-cli scaler run` command. This command continuously polls Prometheus for metrics (like HTTP requests per second) and compares them against predefined thresholds to automatically increase or decrease the number of replicas for a target service.


