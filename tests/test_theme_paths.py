"""Tests for theme path discovery."""

from __future__ import annotations

from pathlib import Path

from conftest import load_ha_utils_module

theme_paths = load_ha_utils_module("theme_paths")
discover_theme_sources = theme_paths.discover_theme_sources


def test_discover_include_dir_merge_named(tmp_path: Path) -> None:
    themes = tmp_path / "themes"
    themes.mkdir()
    (themes / "one.yaml").write_text("one: {}\n", encoding="utf-8")

    config = """
frontend:
  themes: !include_dir_merge_named themes
"""
    sources = discover_theme_sources(tmp_path, config)
    assert themes in sources


def test_discover_include_single_file(tmp_path: Path) -> None:
    theme_file = tmp_path / "themes.yaml"
    theme_file.write_text("my_theme: {}\n", encoding="utf-8")

    config = """
frontend:
  themes: !include themes.yaml
"""
    sources = discover_theme_sources(tmp_path, config)
    assert theme_file in sources


def test_discover_common_fallback_dir(tmp_path: Path) -> None:
    themes = tmp_path / "themes"
    themes.mkdir()

    sources = discover_theme_sources(tmp_path, None)
    assert themes in sources


def test_discover_empty_when_nothing_exists(tmp_path: Path) -> None:
    sources = discover_theme_sources(tmp_path, None)
    assert sources == []
