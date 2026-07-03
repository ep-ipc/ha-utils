"""Tests for theme typography patching."""

from __future__ import annotations

from pathlib import Path

from conftest import REPO, load_ha_utils_module

theme_patcher = load_ha_utils_module("theme_patcher")
apply_typography_patches = theme_patcher.apply_typography_patches
patch_all_themes = theme_patcher.patch_all_themes

FIXTURE = (REPO / "tests" / "fixtures" / "sample_theme.yaml").read_text(
    encoding="utf-8"
)


def test_apply_typography_patches_scale_and_calc() -> None:
    result = apply_typography_patches(FIXTURE, scale=1.2, line_height=1.8)
    assert "ha-font-size-scale: 1.2" in result
    assert "ha-line-height-normal: 1.8" in result
    assert "calc(14px * var(--ha-font-size-scale))" in result
    assert "calc(18px * var(--ha-font-size-scale))" in result


def test_apply_typography_patches_mushroom_ha_vars() -> None:
    result = apply_typography_patches(FIXTURE, scale=1.0, line_height=1.8)
    assert "mush-card-primary-font-size: 'var(--ha-font-size-l)'" in result


def test_patch_all_themes_dry_run(tmp_path: Path) -> None:
    themes_dir = tmp_path / "themes"
    themes_dir.mkdir()
    theme_file = themes_dir / "sample.yaml"
    theme_file.write_text(FIXTURE, encoding="utf-8")

    result = patch_all_themes(
        themes_dir, scale=1.5, line_height=2.0, dry_run=True
    )
    assert result.would_change == ["sample.yaml"]
    assert theme_file.read_text(encoding="utf-8") == FIXTURE


def test_patch_all_themes_apply_writes_and_backup(tmp_path: Path) -> None:
    themes_dir = tmp_path / "themes"
    themes_dir.mkdir()
    theme_file = themes_dir / "sample.yaml"
    theme_file.write_text(FIXTURE, encoding="utf-8")

    result = patch_all_themes(
        themes_dir, scale=1.5, line_height=2.0, dry_run=False
    )
    assert result.changed == ["sample.yaml"]
    assert (themes_dir / "sample.yaml.bak").is_file()
    assert "ha-font-size-scale: 1.5" in theme_file.read_text(encoding="utf-8")


def test_patch_all_themes_missing_dir() -> None:
    result = patch_all_themes(
        Path("/nonexistent/themes"), scale=1.0, dry_run=True
    )
    assert result.errors
