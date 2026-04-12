#!/usr/bin/env python3
"""Helm — Harness Engineering Agent Framework.

Usage:
    python cli.py
    python cli.py --tools-profile minimal
    python cli.py --team-id T1 --channel-id C1
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "src"))

from teambot.app.tui import main

if __name__ == "__main__":
    main()
