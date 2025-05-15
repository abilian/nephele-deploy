# inventory.py

# OPTION 1: Define hosts here if you run `pyinfra inventory.py deploy.py ...`
# Replace with your server details.
# hosts = [
#     "your_admin_user@your_server_ip_or_hostname" # Simple case
# ]

# Or with specific data, for example, if the SSH connection IP is different from the public IP for the Makefile:
# hosts = {
# 'smo_server_alias': {
# 'ssh_host': 'internal_ip_or_dns_for_ssh', # Actual address to connect to
# 'ssh_user': 'your_admin_user_with_sudo',
# 'public_ip': '188.165.223.31' # The IP for the Makefile
#     }
# }
# If using this, the deploy.py will pick up `host.data.public_ip`.

# OPTION 2: Target directly on CLI (no inventory.py strictly needed for one host)
# `pyinfra 188.165.223.31 --user root deploy.py
# In this case, `host.name` in deploy.py becomes '188.165.223.31' if that's what you used.

# For this consolidated example, let's assume you'll target directly or
# define a simple list in an inventory.py if you prefer.
# If you use the alias method above, target_ip_for_makefile in deploy.py will use it.


