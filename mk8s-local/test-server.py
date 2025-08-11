#!/usr/bin/env python3

import os
import subprocess
import time

from hcloud import Client
from hcloud.images import Image

HETZNER_TOKEN = os.environ["HETZNER_TOKEN"]
IMAGE = Image(name="ubuntu-24.04")
SERVER_NAME = "nephele-sf-mk8s"

client = Client(token=HETZNER_TOKEN)


def main():
    rebuild_server(SERVER_NAME, IMAGE)

    subprocess.run(["ssh-keygen", "-R", SERVER_NAME], check=True)
    # fix_known_hosts(SERVER_NAME)

    time.sleep(30)  # Wait for the server to be fully rebuilt

    subprocess.run(
        # fmt: off
        [
            "ssh",
            "-o", "StrictHostKeyChecking=accept-new",
            f"root@{SERVER_NAME}",
            "sleep 1",
        ],
        # fmt: on
        check=True,
    )

    print("Syncing local scripts to server...")
    subprocess.run(
        # fmt: off
        [
            "rsync",
            "-e", "ssh",
            "-avz",
            "./local-scripts/",
            f"root@{SERVER_NAME}:/root/local-scripts/",
        ],
        # fmt: on
        check=True,
        input="yes\n",
        text=True,
    )

    run_script("./0-prepare-server.py")
    run_script("./1-create-clusters-on-lxd.py")
    run_script("./2-setup-karmada.py")
    run_script("./3-check-karmada.py")
    run_script("./4-nginx-demo.py")
    run_script("./5-flask-demo-1.py")
    run_script("./5-flask-demo-2.py")

    # run_strip("./8-remove-karmada.py")
    # run_strip("./9-tidy-up.py")


def run_script(cmd: str):
    """
    Runs a command on the server via SSH.
    """
    cmd = "cd /root/local-scripts && " + cmd
    print("Running command on server:", cmd)
    result = subprocess.run(
        ["ssh", "-t", f"root@{SERVER_NAME}", cmd],
        check=True,
        text=True,
        # capture_output=True,
    )
    # print(result.stderr.strip())
    # print(result.stdout.strip())


def rebuild_server(server_name: str, image: Image):
    """
    Rebuilds a server with the specified image.
    """
    servers = client.servers.get_all()
    for server in servers:
        if server.name == server_name:
            print(f"Rebuilding server {server.name} with image {image.name}")
            server.rebuild(image=image)
            return
    print(f"Server {server_name} not found.")


def fix_known_hosts(ip_address: str):
    """
    Fixes the known_hosts file by removing entries for the server.
    """
    known_hosts_path = os.path.expanduser("~/.ssh/known_hosts")
    if os.path.exists(known_hosts_path):
        with open(known_hosts_path, "r") as f:
            lines = f.readlines()
        with open(known_hosts_path, "w") as f:
            for line in lines:
                if line.startswith(ip_address):
                    continue
                f.write(line)


if __name__ == "__main__":
    main()
