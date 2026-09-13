#!/usr/bin/env python
"""Entrypoint for the Intelligent Profiling Engine CLI.

Supports two modes:

1. Interactive REPL (default):
   ```
   python run.py
   ```

2. Non-interactive scripting (for automation / CI):
   ```
   python run.py --command "profile CUST-1 update --behavior amount:100"
   python run.py -c "stats"
   python run.py --file script.txt     # runs each line as a command
   ```
"""
from __future__ import annotations

import argparse
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "src"))

from profile_system.cli import ProfileSystemCLI


def main():
    parser = argparse.ArgumentParser(
        prog="profile-system",
        description="Intelligent Profiling Engine CLI",
    )
    parser.add_argument(
        "-c", "--command",
        help="Run a single command non-interactively and exit.",
    )
    parser.add_argument(
        "-f", "--file",
        help="Run commands from a script file (one command per line).",
    )
    args = parser.parse_args()

    cli = ProfileSystemCLI()

    if args.command:
        # Non-interactive single command.
        cli.process_command(args.command)
        return

    if args.file:
        if not os.path.exists(args.file):
            print(f"✖ Script file not found: {args.file}")
            sys.exit(1)
        with open(args.file, encoding="utf-8") as f:
            for lineno, line in enumerate(f, 1):
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                try:
                    cli.process_command(line)
                except Exception as e:
                    print(f"✖ Line {lineno} error: {e}")
        return

    # Interactive REPL.
    cli.run()


if __name__ == "__main__":
    main()
