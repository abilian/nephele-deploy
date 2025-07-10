# TODO (Next Steps, for Stage 3)

To conduct additional tests and validation experiments (Stage 3 of the H3NI project), we will need to be able to deploy our demos on "real" Kubernetes instances. The current scripts are have parts specific to a self-contained `KinD` (Kubernetes in Docker) environment.

-> Here's a list of action items to adapt the scripts to `microk8s`, `k3s`, or managed cloud clusters.

### 1. Refactor and Generalize Core Scripts `[High Priority]`

The first step is to remove hardcoded, `KinD`-specific logic from the existing scripts to make them more modular and reusable.

- [ ] **Isolate `KinD`-Specific Commands:**
    -   Cf. the `kind create cluster` commands in `1-deploy-karmada-on-kind.py` and `6-install-some-kind-cluster.py`.

- [ ] **Abstract Kubeconfig Paths:**
    -   Check if `/root/.kube/karmada-apiserver.config` and `~/.kube/config` will still work on other k8s distros.

### 2. Add Support for `microk8s` `[High Priority]`

`microk8s` is an excellent first target for a "real" Kubernetes instance. It's a single-package install and manages its own dependencies well.

- [ ] **Create a `deploy-microk8s.py` Script:**
    -   It should include `snap install microk8s --classic`.
    -   It must enable required addons: `microk8s enable dns hostpath-storage registry`. The built-in registry is crucial as it replaces the standalone Docker registry used for `KinD`.
    -   Add a `microk8s status --wait-ready` check to ensure the cluster is stable before proceeding.

- [ ] **Adapt Karmada Installation for `microk8s`:**
    -   Create a new script, e.g., `2-deploy-karmada-on-mk8s.py`.
    -   This script will assume `microk8s` is already running. It will use `microk8s.kubectl` to apply the Karmada components directly onto the `microk8s` cluster.
    -   It will need to handle generating the correct kubeconfig (`microk8s config > /root/.kube/config`).

- [ ] **Update Demo Build Script for `microk8s` Registry:**
    -   The `microk8s` registry runs at `localhost:32000`. The script `7-build-bxl-demo...` needs to be adapted or duplicated to push images to this new endpoint instead of `localhost:5000`.

### 3. Address Networking and Registry Challenges `[Medium Priority]`

Moving beyond a single-node `KinD` setup introduces networking complexities.

- [ ] **Dynamically Configure Insecure Registries:**
    -   The `0-setup-server.py` script hardcodes `127.0.0.1:5000` in `/etc/docker/daemon.json`.
    -   This should be updated to use the host's actual network IP address (e.g., `eth0`), which can be discovered using `pyinfra.facts.hardware.Ipv4Addrs`. This is mandatory for multi-node clusters where workers need to pull from a registry on the control-plane node.

- [ ] **Review and Document Service Exposure:**
    -   The Prometheus script (`2-install-prometheus-on-kind.py`) uses `type: NodePort`. On `KinD`, this is accessed via `localhost`. On a real server, it will be `http://<server_ip>:<node_port>`.
    -   Document this clearly and ensure all services that need to be accessed externally are configured with either `NodePort` or `LoadBalancer`.

### 4. Update Deployment Workflows and Documentation `[Medium Priority]`

- [ ] Create New `Makefile` Targets
- [ ] Update `README.md`
