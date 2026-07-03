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
    assert "filename" not in hacs
    assert manifest.is_file()
    assert THEME_FILE.is_file()


def test_bundled_theme_deploys_to_config_themes(tmp_path: Path) -> None:
    deploy_bundled_assets = load_ha_utils_module("deploy").deploy_bundled_assets

    hass = types.SimpleNamespace(
        config=types.SimpleNamespace(config_dir=str(tmp_path))
    )

    result = deploy_bundled_assets(hass)

    assert result.errors == []
    assert result.copied == ["themes/ha_utils_font_scale.yaml"]
    assert (tmp_path / "themes" / "ha_utils_font_scale.yaml").read_text(
        encoding="utf-8"
    ) == THEME_FILE.read_text(encoding="utf-8")
