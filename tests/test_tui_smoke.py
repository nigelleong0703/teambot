from __future__ import annotations

import re

import pytest


def test_tui_uses_blue_accent_color():
    """Helm uses a blue accent, not amber."""
    from teambot.app.tui import _ANSI_STYLES

    accent = _ANSI_STYLES["accent"]
    old_amber_codes = {"180", "215", "221", "229", "230"}
    codes = set(re.findall(r"\d+", accent))
    assert not codes & old_amber_codes, f"accent still uses amber code: {accent}"
