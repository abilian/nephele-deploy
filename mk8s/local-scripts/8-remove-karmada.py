#!/usr/bin/env python3

import subprocess

# Define the command and its arguments as a list to prevent shell injection.
kubectl_command = [
    "kubectl",
    "--kubeconfig",
    "/var/snap/microk8s/current/credentials/client.config",
    "delete",
    "namespace",
    "karmada-system",
    "--ignore-not-found=true",
]

try:
    result = subprocess.run(
        kubectl_command,
        input="yes\n",  # Pass the string "yes" followed by a newline to stdin.
        text=True,  # Ensure input/output are treated as text.
        capture_output=True,  # Capture stdout and stderr.
        check=True,  # Raise CalledProcessError if the command fails.
    )

    print("Namespace 'karmada-system' deleted successfully.")
    print("Output:\n", result.stdout)

except FileNotFoundError:
    print("Error: 'kubectl' command not found. Is it installed and in your PATH?")
except subprocess.CalledProcessError as e:
    print(f"Command failed with return code {e.returncode}")
    print(f"Error output:\n{e.stderr}")
