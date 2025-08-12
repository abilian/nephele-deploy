# System Architecture and Technical Overview

> Note: read this document after the [README](./README.md) to understand the overall system architecture and design patterns.

This document provides a deeper look into the architecture of the MicroK8s/LXD testbed, its key design patterns, and a guide for troubleshooting.

### Component Breakdown

The system is a "cluster of clusters" built with the following components:

*   **Host Server**: A standard Ubuntu/Debian machine that provides the physical resources.
*   **Host Cluster (MicroK8s)**: A single MicroK8s cluster running directly on the host. Its sole purpose is to provide a stable Kubernetes environment for the Karmada control plane. It does not run user applications.
*   **Karmada Control Plane**: A set of pods deployed into the `karmada-system` namespace on the Host Cluster. This acts as the "brain" of the federation, providing a unified API to manage all member clusters.
*   **Member Clusters (MicroK8s in LXD)**: Three fully independent MicroK8s clusters (`member1`, `member2`, `member3`), each running inside its own LXD system container. This provides strong process and network isolation, simulating a realistic multi-cluster topology. These are the "worker" clusters that run the actual applications.

### Critical Design Pattern: Networking via LXD Proxy

Connectivity between the host and the isolated member clusters is the most critical part of this architecture. Instead of relying on potentially problematic Kubernetes `NodePort` or `LoadBalancer` services within a nested environment, this testbed uses **LXD proxy devices** for all external access. This creates a direct, reliable, and debuggable network path.

Two distinct proxy patterns are used:

1.  **Management Access (API Server Proxy)**: To allow `kubectl` and `karmadactl` on the host to manage the member clusters, a proxy forwards a unique port on the host (e.g., `localhost:16441`) to the internal Kubernetes API server running on `127.0.0.1:16443` *inside* the respective LXD container.

2.  **Application Access (Direct-to-Pod Proxy)**: To expose applications like Prometheus, a proxy forwards a unique port on the host (e.g., `localhost:9091`) **directly to the Prometheus pod's internal IP and application port** (e.g., `10.1.33.11:9090`). This robust pattern bypasses the Kubernetes service networking layer entirely, guaranteeing connectivity as long as the pod is running.

### Critical Design Pattern: Custom Image Distribution

To deploy custom-built applications (like the second Flask demo) without the complexity of a networked container registry, the testbed uses a simple and effective `build -> save -> push -> import` workflow:
1.  The custom image is built locally on the host using **Docker**.
2.  The image is saved to a `.tar` archive using `docker save`.
3.  The `.tar` file is pushed into the filesystem of each LXD container using `lxc file push`.
4.  The image is imported directly into each member cluster's internal image cache using `microk8s images import`.

This makes the application deployment process self-contained and resilient to network issues.

### Troubleshooting Guide

If a script fails, follow this process to diagnose the issue, working from the outside in.

1.  **Check the Host and LXD Containers**
    *   Are all LXD containers running?
        ```bash
        lxc list
        ```    *   Are the host ports for the proxies open? (e.g., for `member1`'s API and Prometheus)
        ```bash
        ss -tlpn | grep ':16441'
        ss -tlpn | grep ':9091'
        ```

2.  **Check the Karmada Federation**
    *   Set your KUBECONFIG to the Karmada control plane:
        ```bash
        export KUBECONFIG=/etc/karmada/karmada-apiserver.config
        ```
    *   Are all clusters registered and `Ready`?
        ```bash
        kubectl get clusters
        ```

3.  **Check Inside a Member Cluster**
    *   Are the pods running in the `monitoring` namespace on `member1`?
        ```bash
        kubectl --kubeconfig /root/member1.config get pods -n monitoring
        ```
    *   **The Most Powerful Tool:** If a pod is stuck (e.g., `Pending`, `ImagePullBackOff`, `CrashLoopBackOff`), use `describe` to see its events. This will almost always tell you the root cause.
        ```bash
        # Get the full pod name first
        POD_NAME=$(kubectl --kubeconfig /root/member1.config get pods -n monitoring -o jsonpath='{.items[0].metadata.name}')
        
        # Describe the pod
        kubectl --kubeconfig /root/member1.config describe pod $POD_NAME -n monitoring
        ```

4.  **Direct Connection Test (`port-forward`)**
    *   To bypass all LXD proxies and test if an application pod is healthy, use `kubectl port-forward`. This creates a direct tunnel to the pod.
        ```bash
        # In one terminal:
        POD_NAME=$(kubectl --kubeconfig /root/member1.config get pods -n monitoring -l app.kubernetes.io/name=prometheus -o jsonpath='{.items[0].metadata.name}')
        kubectl --kubeconfig /root/member1.config port-forward -n monitoring $POD_NAME 8888:9090

        # In a second terminal, test the connection:
        curl http://localhost:8888/
        ```    
    *   If this works, but accessing via the host port (e.g., `9091`) fails, the problem is with the LXD proxy configuration. If this fails, the problem is inside the pod itself
