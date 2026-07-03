"""Tests for the HA Utils font-scale theme pack."""

from __future__ import annotations

import json
import importlib.util
import re
import sys
import types
from pathlib import Path


REPO = Path(__file__).resolve().parents[1]
THEME_FILE = (
    REPO
    / "custom_components"
    / "ha_utils"
    / "bundled"
    / "themes"
    / "ha_utils_font_scale.yaml"
)
BLUEPRINT_DIR = (
    REPO
    / "custom_components"
    / "ha_utils"
    / "bundled"
    / "blueprints"
    / "automation"
    / "ha_utils"
)
BLUEPRINT_FILES = [
    "cold_day.yaml",
    "high_wind.yaml",
    "hot_day.yaml",
    "possible_thunderstorm.yaml",
]


def load_ha_utils_module(name: str):
    """Load a ha_utils module without importing Home Assistant."""
    package_name = "custom_components.ha_utils"
    if package_name not in sys.modules:
        package = types.ModuleType(package_name)
        package.__path__ = [str(REPO / "custom_components" / "ha_utils")]  # type: ignore[attr-defined]
        sys.modules[package_name] = package

    module_name = f"{package_name}.{name}"
    spec = importlib.util.spec_from_file_location(
        module_name,
        REPO / "custom_components" / "ha_utils" / f"{name}.py",
    )
    if spec is None or spec.loader is None:
        raise ImportError(f"Cannot load {module_name}")

    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


def test_theme_file_contains_expected_scale_variants() -> None:
    text = THEME_FILE.read_text(encoding="utf-8")
    names = re.findall(
        r'^"HA Font (\d+)%":$',
        text,
        flags=re.MULTILINE,
    )

    assert names == ["100", "110", "115", "120", "125", "130", "140", "150"]
    assert text.count("ha-font-size-scale:") == len(names) * 2


def test_theme_file_only_sets_font_scale_inside_modes() -> None:
    text = THEME_FILE.read_text(encoding="utf-8")

    assert text.count("modes:") == 8
    assert text.count("light:") == 8
    assert text.count("dark:") == 8
    assert re.findall(
        r"^\s+ha-font-size-scale:\s",
        text,
        flags=re.MULTILINE,
    )


def test_hacs_metadata_points_to_theme_file() -> None:
    hacs = json.loads((REPO / "hacs.json").read_text(encoding="utf-8"))

    manifest = (
        REPO / "custom_components" / "ha_utils" / "manifest.json"
    )
    assert hacs["name"] == "Home Assistant Utils"
    assert hacs["content_in_root"] is False
    assert "filename" not in hacs
    assert manifest.is_file()
    assert THEME_FILE.is_file()
    for blueprint in BLUEPRINT_FILES:
        assert (BLUEPRINT_DIR / blueprint).is_file()


def test_manifest_has_hacs_required_keys() -> None:
    manifest = json.loads(
        (
            REPO / "custom_components" / "ha_utils" / "manifest.json"
        ).read_text(encoding="utf-8")
    )

    assert manifest["domain"] == "ha_utils"
    for key in (
        "codeowners",
        "documentation",
        "issue_tracker",
        "name",
        "version",
    ):
        assert key in manifest


def test_bundled_resources_deploy_to_config(tmp_path: Path) -> None:
    deploy_bundled_assets = load_ha_utils_module("deploy").deploy_bundled_assets

    hass = types.SimpleNamespace(
        config=types.SimpleNamespace(config_dir=str(tmp_path))
    )

    result = deploy_bundled_assets(hass)

    expected = [
        f"blueprints/automation/ha_utils/{name}"
        for name in BLUEPRINT_FILES
    ] + ["themes/ha_utils_font_scale.yaml"]

    assert result.errors == []
    assert result.copied == expected
    assert (tmp_path / "themes" / "ha_utils_font_scale.yaml").read_text(
        encoding="utf-8"
    ) == THEME_FILE.read_text(encoding="utf-8")
    for blueprint in BLUEPRINT_FILES:
        assert (
            tmp_path / "blueprints" / "automation" / "ha_utils" / blueprint
        ).is_file()


def test_deploy_copies_missing_files_without_overwriting(tmp_path: Path) -> None:
    deploy_bundled_assets = load_ha_utils_module("deploy").deploy_bundled_assets
    hass = types.SimpleNamespace(
        config=types.SimpleNamespace(config_dir=str(tmp_path))
    )

    first = deploy_bundled_assets(hass)
    second = deploy_bundled_assets(hass)

    assert first.errors == []
    assert second.copied == []
    assert sorted(second.skipped) == sorted(first.copied)

    missing = tmp_path / "blueprints" / "automation" / "ha_utils" / "hot_day.yaml"
    missing.unlink()

    third = deploy_bundled_assets(hass)

    assert third.copied == ["blueprints/automation/ha_utils/hot_day.yaml"]
    assert missing.is_file()
