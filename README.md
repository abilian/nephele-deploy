# Deployment Script for the SMO

These scripts are designed to deploy the NEPHELE infrastructure, the SMO (Service Management Operations) and any additional demo on a server. They PyInfra for deployment and assumes you have a working SSH connection to the target server.

## Status

Not finished yet. This is a work in progress and not ready for production use.

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
