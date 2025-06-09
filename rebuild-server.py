#!/usr/bin/env python3

import os

from hcloud import Client
from hcloud.images import Image

HETZNER_TOKEN = os.environ["HETZNER_TOKEN"]
IMAGE = Image(name="ubuntu-22.04")
SERVER_NAME = "nephele1"
IP_ADDRESS = "157.180.84.240"

client = Client(token=HETZNER_TOKEN)


def main():
    rebuild_server(SERVER_NAME, IMAGE)
    fix_known_hosts(IP_ADDRESS)


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

# servers = client.servers.get_all()
# for server in servers:
#     print(f"{server.id=} {server.name=} {server.status=}")
#     if server.name == "nephele1":
#         print(f"Rebuilding server {server.name} with image {IMAGE.name}")
#         server.rebuild(image=IMAGE)
