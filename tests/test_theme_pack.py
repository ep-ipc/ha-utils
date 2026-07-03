"""Tests for the HA Utils font-scale theme pack."""

from __future__ import annotations

import re
from pathlib import Path


THEME_FILE = Path(__file__).resolve().parents[1] / "themes" / "ha_utils_font_scale.yaml"


def test_theme_file_contains_expected_scale_variants() -> None:
    text = THEME_FILE.read_text(encoding="utf-8")
    names = re.findall(
        r'^"HA Utils Default Font (\d+)%":$',
        text,
        flags=re.MULTILINE,
    )

    assert names == ["100", "110", "115", "120", "125", "130", "140", "150"]
    assert text.count("ha-font-size-scale:") == len(names)


def test_theme_file_only_sets_font_scale() -> None:
    text = THEME_FILE.read_text(encoding="utf-8")
    theme_keys = [
        line.strip().split(":", 1)[0]
        for line in text.splitlines()
        if line.startswith("  ") and ":" in line
    ]

    assert set(theme_keys) == {"ha-font-size-scale"}
