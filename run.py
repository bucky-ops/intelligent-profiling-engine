#!/usr/bin/env python
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from profile_system.cli import ProfileSystemCLI

if __name__ == "__main__":
    cli = ProfileSystemCLI()
    cli.run()