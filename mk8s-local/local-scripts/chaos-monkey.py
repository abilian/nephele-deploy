#!/usr/bin/env python3

"""
A Chaos Monkey for the Karmada testbed.

This script simulates infrastructure failures by periodically and randomly stopping
and starting the LXD containers that host the member clusters. This is useful
for testing the resilience and recovery behavior of the Karmada control plane
and any deployed applications.

The script runs in an infinite loop. Press Ctrl+C to stop it gracefully.

Usage:
    # Run with default settings (10-minute interval, 10% down probability)
    sudo ./chaos-monkey.py

    # Run every 30 seconds with a 50% chance of taking a cluster down
    sudo ./chaos-monkey.py --interval 30 --down-probability 0.5

    # Target only specific clusters
    sudo ./chaos-monkey.py --clusters member1 member3
"""

import sys
import time
import random
import argparse
from datetime import datetime

# Import shared configuration and helpers
from common import run_command, check_root_privileges, print_color, colors
from config import MEMBER_CLUSTERS


def main():
    """Main execution function."""
    check_root_privileges("chaos-monkey.py")

    # --- Argument Parsing for Configuration ---
    parser = argparse.ArgumentParser(
        description="A Chaos Monkey to simulate member cluster failures.",
        formatter_class=argparse.RawTextHelpFormatter,
    )
    parser.add_argument(
        "--interval",
        type=int,
        default=600,
        help="Interval in seconds between chaos events. Default: 600 (10 minutes).",
    )
    parser.add_argument(
        "--down-probability",
        type=float,
        default=0.1,
        help="Probability (0.0 to 1.0) for a cluster to be down. Default: 0.1 (10%%).",
    )
    parser.add_argument(
        "--clusters",
        nargs="+",
        default=MEMBER_CLUSTERS,
        help=f"A list of member clusters to target. Default: {' '.join(MEMBER_CLUSTERS)}",
    )
    args = parser.parse_args()

    if not (0.0 <= args.down_probability <= 1.0):
        print_color(
            colors.RED, "FATAL: --down-probability must be between 0.0 and 1.0."
        )
        sys.exit(1)

    print_color(colors.BLUE, "========================================================")
    print_color(colors.BLUE, "🐒 Chaos Monkey is starting its mischief! 🐒")
    print_color(colors.BLUE, "========================================================")
    print(f"Targeting clusters: {', '.join(args.clusters)}")
    print(f"Run interval: {args.interval} seconds")
    print(f"Down probability: {args.down_probability * 100}%")
    print_color(colors.YELLOW, "Press Ctrl+C to stop the monkey.")

    try:
        while True:
            apply_chaos(args)
            time.sleep(args.interval)

    except KeyboardInterrupt:
        print_color(
            colors.GREEN,
            "\n\n🐒 Chaos Monkey received Ctrl+C. Shutting down gracefully. 🐒",
        )
        sys.exit(0)
    except Exception as e:
        print_color(colors.RED, f"\nAn unexpected error occurred: {e}")
        sys.exit(1)


def apply_chaos(args):
    print_color(
        colors.YELLOW,
        f"\n[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] --- The monkey is waking up! ---",
    )
    for cluster in args.clusters:
        current_state = get_cluster_state(cluster)
        if current_state == "UNKNOWN":
            print_color(
                colors.RED, f"  - Skipping '{cluster}': LXD container not found."
            )
            continue

        # Determine the desired state based on probability
        roll = random.random()
        if roll < args.down_probability:
            desired_state = "STOPPED"
        else:
            desired_state = "RUNNING"

        # Take action only if the state needs to change
        if desired_state == "STOPPED" and current_state == "RUNNING":
            print_color(colors.RED, f"  - Taking '{cluster}' OFFLINE...")
            run_command(["lxc", "stop", cluster])
        elif desired_state == "RUNNING" and current_state == "STOPPED":
            print_color(colors.GREEN, f"  - Bringing '{cluster}' ONLINE...")
            run_command(["lxc", "start", cluster])
        else:
            # State is already as desired, do nothing
            print(f"  - Keeping '{cluster}' in its current state: {current_state}")
    print_color(
        colors.BLUE,
        f"\n[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] --- The monkey is going to sleep for {args.interval} seconds... ---",
    )


def get_cluster_state(cluster_name):
    """
    Checks the current state of an LXD container.
    Returns 'RUNNING', 'STOPPED', or 'UNKNOWN'.
    """
    result = run_command(
        ["lxc", "info", cluster_name], check=False, capture_output=True
    )
    if result.returncode != 0:
        return "UNKNOWN"

    for line in result.stdout.splitlines():
        if line.strip().startswith("Status:"):
            return line.split()[-1]
    return "UNKNOWN"


if __name__ == "__main__":
    main()
