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
    command, check=True, command_input=None, env=None, capture_output=False
):
    """A comprehensive helper to run a shell command and handle errors."""
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
            text=True,
            env=process_env,
            capture_output=capture_output,
        )
        return result
    except FileNotFoundError:
        print_color(
            colors.RED, f"FATAL: Command '{command[0]}' not found. Is it in your PATH?"
        )
        sys.exit(1)
    except subprocess.CalledProcessError as e:
        if capture_output and e.stderr:
            print_color(colors.RED, f"Stderr:\n{e.stderr}")
        if check:
            print_color(
                colors.RED, f"FATAL: Command failed with return code {e.returncode}."
            )
            sys.exit(1)
        return e


def command_exists(command):
    """Checks if a command is available in the system's PATH."""
    return shutil.which(command) is not None


def check_root_privileges(script_name="This script"):
    """Checks for root privileges and exits if not found."""
    if os.geteuid() != 0:
        print_color(colors.RED, f"FATAL: {script_name} must be run as the 'root' user.")
        sys.exit(1)
