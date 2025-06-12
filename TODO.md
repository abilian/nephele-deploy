# Roadmap to a Full Installation

See: https://gitlab.eclipse.org/eclipse-research-labs/nephele-project/smo/-/blob/main/README.md

To bridge the gaps, we need to create a new script, e.g., `3-deploy-smo.py` and update the existinog ones:

1.  **Update `0-setup-server.py`:**
    *   Use `files.line` or `files.file` to ensure `/etc/docker/daemon.json` contains the `insecure-registries` configuration.
    *   Use `systemd.service` to restart the `docker` service.
    *   Implement the `containerd` configuration steps using `files.directory` and `files.put` to create the `hosts.toml` file.
    *   Restart the `containerd` or `microk8s` service.

2.  **Update `2-deploy-karmada-on-mk8s.py`:**
    *   Add `server.shell` operations to run the sequence of `kubectl apply` commands for the Prometheus CRDs, targeting the Karmada kubeconfig.
    *   Investigate the installation process for Submariner (e.g., using `subctl` or a Helm chart) and add it to this script.

3.  **Create a New Script `3-deploy-smo-and-demo.py`:**
    *   **Configure SMO:** Use `files.template` to generate the `config/flask.env` file, populating the `KARMADA_KUBECONFIG` variable correctly.
    *   **Deploy SMO:** Use `server.shell` to run `docker compose up -d` from the root of the SMO repository.
    *   **Deploy Brussels Demo:** Use `server.shell` to execute the remaining `make` targets from the `examples/brussels-demo` directory:
        *   `make change-ips`
        *   `make push-artifacts`
    *   **Trigger Deployment:** Finally, use `server.shell` to execute the `create-existing-artifact.sh` script to test the full end-to-end flow.
