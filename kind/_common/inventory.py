# inventory.py
# See: https://docs.pyinfra.com/en/3.x/inventory-data.html

import os

_default_hostname = "nephele"
_hostname = os.getenv("SERVER_NAME", _default_hostname)

__all__ = ["hosts"]

hosts = [
    # List of hosts in the inventory.
    _hostname,
]
