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


def test_welcome_shows_helm_branding():
    """Tests the full two-column path (terminal_width=130 forces inner_width=108 >= 104)."""
    from teambot.app.tui import TranscriptRenderer

    renderer = TranscriptRenderer(model_name="test-model", loaded_skills_count=0, terminal_width=130)
    welcome = renderer.render_welcome()
    assert "Helm" in welcome
    assert "TeamBot" not in welcome


def test_compact_welcome_shows_helm_branding():
    """terminal_width=60 → inner_width=56 < 104 → compact path."""
    from teambot.app.tui import TranscriptRenderer

    renderer = TranscriptRenderer(model_name="test-model", loaded_skills_count=0, terminal_width=60)
    welcome = renderer.render_welcome()
    assert "Helm" in welcome
    assert "TeamBot" not in welcome
    # Compact path uses single-column box (no double │ ... │ ... │ rows)
    double_col_rows = [ln for ln in welcome.splitlines() if ln.count("│") >= 3]
    assert not double_col_rows, "Expected compact single-column layout"
