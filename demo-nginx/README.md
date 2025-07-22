# Test of KinD cluster

These scripts are intended to demonstrate the basic setup of a KinD cluster. They should display the initial Nginx homepage at the end of the sequence.

Scripts require `pyinfra` on the local host.

Remote server requirements:

- **Ubuntu** or **Debian** server.

- SSH access with `root` privileges. All scripts are designed to be run as the `root` user.


## Usage

Configure `inventory.py` or set an environment variable with the name or IP address of target server. This should match the host defined in `kind-scripts/inventory.py`.

```bash
export SERVER_NAME=my-server
```

## Run the Deployment

Execute the all-in-one command to deploy the entire environment:

```bash
make
```
