import os
import sys
import subprocess
import shutil


# --- ANSI Color Codes for Better Output ---
class colors:
    GREEN = "\033[92m"
    RED = "\033[91m"
    YELLOW = "\033[93m"
    BLUE = "\033[94m"
    ENDC = "\033[0m"


def print_color(color, message):
    """Prints a message in a given color."""
    print(f"{color}{message}{colors.ENDC}")


def run_command(
    command, check=True, capture_output=False, command_input=None, text=True, env=None
):
    """
    A comprehensive helper to run a shell command and handle errors.
    It combines the functionality from all scripts.
    """
    display_command = " ".join(command)
    if command_input:
        display_command += " <<< [INPUT]"

    print_color(colors.BLUE, f"--> Executing: {display_command}")

    try:
        process_env = os.environ.copy()
        if env:
            process_env.update(env)

        result = subprocess.run(
            command,
            input=command_input,
            check=check,
            capture_output=capture_output,
            text=text,
            env=process_env,
        )
        return result
    except FileNotFoundError:
        print_color(
            colors.RED, f"FATAL: Command '{command[0]}' not found. Is it in your PATH?"
        )
        sys.exit(1)
    except subprocess.CalledProcessError as e:
        print_color(colors.RED, f"FATAL: Command failed: {' '.join(command)}")
        print_color(colors.RED, f"Return code: {e.returncode}")
        if e.stdout:
            print(f"Stdout:\n{e.stdout}")
        if e.stderr:
            print(f"Stderr:\n{e.stderr}")
        sys.exit(1)


def command_exists(command):
    """Checks if a command is available in the system's PATH."""
    return shutil.which(command) is not None


def check_root_privileges(script_name="This script"):
    """Checks for root privileges and exits if not found."""
    if os.geteuid() != 0:
        print_color(
            colors.RED,
            f"FATAL: {script_name} must be run as the 'root' user or with sudo.",
        )
        sys.exit(1)
