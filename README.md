# Deployment scripts for the SMO project

These scripts are designed to deploy the NEPHELE infrastructure, the SMO (Service Management Operations) and any additional demo on a server. They PyInfra for deployment and assumes you have a working SSH connection to the target server.

Available scripts:

-   `deploy-docker.py`
-   `eploy-brussels.py`
-   `deploy-mk8s.py`
-   `deploy-infra.py`


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
