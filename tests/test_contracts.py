"""Contracts for config entities, docs, and bundled layout.

These do not need Home Assistant. They catch renames and missing pieces
before a release.
"""

from __future__ import annotations

import ast
import json
import re
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
HA_UTILS = REPO / "custom_components" / "ha_utils"
BUNDLED = HA_UTILS / "bundled"


def _string_assigns(path: Path, target: str) -> list[tuple[str, ...]]:
    """Return string tuples assigned to a module-level name like `_WIND`."""

    tree = ast.parse(path.read_text(encoding="utf-8"))
    for node in tree.body:
        if not isinstance(node, ast.Assign):
            continue
        for name in node.targets:
            if isinstance(name, ast.Name) and name.id == target:
                assert isinstance(node.value, (ast.Tuple, ast.List))
                rows: list[tuple[str, ...]] = []
                for elt in node.value.elts:
                    assert isinstance(elt, (ast.Tuple, ast.List))
                    rows.append(
                        tuple(
                            item.value
                            for item in elt.elts
                            if isinstance(item, ast.Constant) and isinstance(item.value, str)
                        )
                    )
                return rows
    raise AssertionError(f"{target} not found in {path}")


def _named_string_kwargs(path: Path, key: str = "name") -> list[str]:
    """Collect `name=\"...\"` keyword values from SourceSelect construction."""

    text = path.read_text(encoding="utf-8")
    return re.findall(rf'\b{key}="([^"]+)"', text)


def test_wind_threshold_defaults_and_keys() -> None:
    rows = _string_assigns(HA_UTILS / "number.py", "_WIND")
    by_key = {row[0]: row for row in rows}
    assert list(by_key) == ["rise_big", "rise_all", "fall_all", "fall_big"]
    assert by_key["rise_big"][1] == "Rise to advisory"
    assert by_key["rise_all"][1] == "Rise to warning"
    assert by_key["fall_all"][1] == "Fall from warning"
    assert by_key["fall_big"][1] == "Fall to safe"

    tree = ast.parse((HA_UTILS / "number.py").read_text(encoding="utf-8"))
    defaults: dict[str, float] = {}
    for node in tree.body:
        if not isinstance(node, ast.Assign):
            continue
        for name in node.targets:
            if isinstance(name, ast.Name) and name.id == "_WIND":
                for elt in node.value.elts:
                    key = elt.elts[0].value
                    defaults[key] = elt.elts[2].value
    assert defaults == {
        "rise_big": 30,
        "rise_all": 60,
        "fall_all": 45,
        "fall_big": 20,
    }


def test_temperature_threshold_defaults() -> None:
    rows = _string_assigns(HA_UTILS / "number.py", "_TEMPERATURE")
    assert rows[0][0] == "hot_threshold" and rows[0][1] == "Hot above"
    assert rows[1][0] == "cold_threshold" and rows[1][1] == "Cold below"
    tree = ast.parse((HA_UTILS / "number.py").read_text(encoding="utf-8"))
    for node in tree.body:
        if not isinstance(node, ast.Assign):
            continue
        for name in node.targets:
            if isinstance(name, ast.Name) and name.id == "_TEMPERATURE":
                assert node.value.elts[0].elts[2].value == 90
                assert node.value.elts[1].elts[2].value == 32


def test_config_names_sort_into_source_and_threshold_groups() -> None:
    """Home Assistant sorts Configuration by name; keep groups contiguous."""

    select_names = set(_named_string_kwargs(HA_UTILS / "select.py"))
    assert "Weather station" in select_names
    assert "Weather forecast" in select_names
    assert "Forecast" not in select_names

    wind_names = [
        row[1] for row in _string_assigns(HA_UTILS / "number.py", "_WIND")
    ] + ["Weather forecast", "Weather station"]
    assert wind_names == [
        "Rise to advisory",
        "Rise to warning",
        "Fall from warning",
        "Fall to safe",
        "Weather forecast",
        "Weather station",
    ]
    assert sorted(wind_names, key=str.lower) == [
        "Fall from warning",
        "Fall to safe",
        "Rise to advisory",
        "Rise to warning",
        "Weather forecast",
        "Weather station",
    ]


def test_no_retired_automation_blueprints_bundled() -> None:
    automation = BUNDLED / "blueprints" / "automation"
    assert not automation.exists() or not any(automation.rglob("*.yaml"))
    for name in (
        "high_wind.yaml",
        "hot_day.yaml",
        "cold_day.yaml",
        "possible_thunderstorm.yaml",
    ):
        assert not (BUNDLED / "blueprints" / "automation" / "ha_utils" / name).exists()


def test_only_control_all_script_blueprint_is_bundled() -> None:
    script_dir = BUNDLED / "blueprints" / "script" / "ha_utils"
    assert sorted(p.name for p in script_dir.glob("*.yaml")) == [
        "control_all_by_domain.yaml"
    ]


def test_device_docs_and_const_urls_match() -> None:
    const_text = (HA_UTILS / "const.py").read_text(encoding="utf-8")
    assert 'DOCS_DEVICES = "https://github.com/ep-ipc/ha-utils/blob/main/docs/devices"' in const_text
    for slug in ("wind", "temperature", "bad-weather"):
        assert (REPO / "docs" / "devices" / f"{slug}.md").is_file()


def test_strings_json_lists_signal_subentries() -> None:
    strings = json.loads((HA_UTILS / "strings.json").read_text(encoding="utf-8"))
    subentries = strings["config_subentries"]
    assert set(subentries) >= {"wind_signal", "temperature", "bad_weather"}
    for key in ("temperature", "bad_weather"):
        assert subentries[key]["step"]["user"]["data"]["weather_entity"] == (
            "Weather forecast"
        )
    wind_data = subentries["wind_signal"]["step"]["user"]["data"]
    assert wind_data["rise_big"] == "Rise to advisory"
    assert wind_data["rise_all"] == "Rise to warning"
    assert wind_data["fall_all"] == "Fall from warning"
    assert wind_data["fall_big"] == "Fall to safe"


def test_manifest_version_is_semver_like() -> None:
    manifest = json.loads((HA_UTILS / "manifest.json").read_text(encoding="utf-8"))
    assert re.fullmatch(r"\d+\.\d+\.\d+", manifest["version"])
    assert manifest["domain"] == "ha_utils"
    assert manifest["config_flow"] is True


def test_platforms_declare_expected_entity_files() -> None:
    for platform in ("sensor", "binary_sensor", "number", "select"):
        assert (HA_UTILS / f"{platform}.py").is_file()
    tree = ast.parse((HA_UTILS / "__init__.py").read_text(encoding="utf-8"))
    platforms: list[str] = []
    for node in tree.body:
        if not isinstance(node, ast.AnnAssign):
            continue
        if isinstance(node.target, ast.Name) and node.target.id == "PLATFORMS":
            assert isinstance(node.value, ast.List)
            platforms = [elt.value for elt in node.value.elts if isinstance(elt, ast.Constant)]
    assert platforms == ["sensor", "binary_sensor", "select", "number"]


@pytest.mark.parametrize(
    ("path", "needles"),
    [
        (
            REPO / "docs" / "devices" / "wind.md",
            ["safe", "advisory", "warning", "Risk", "Calm", "Guide"],
        ),
        (
            REPO / "docs" / "devices" / "temperature.md",
            ["Hot", "Cold", "Guide"],
        ),
        (
            REPO / "docs" / "devices" / "bad-weather.md",
            ["Reason", "Guide", "Bad weather"],
        ),
    ],
)
def test_device_docs_cover_published_entities(path: Path, needles: list[str]) -> None:
    text = path.read_text(encoding="utf-8")
    for needle in needles:
        assert needle in text
