"""Tests for runtime font scale helpers."""

from conftest import load_ha_utils_module

load_ha_utils_module("const")
runtime_scale = load_ha_utils_module("runtime_scale")
runtime_scale_payload = runtime_scale.runtime_scale_payload


def test_runtime_scale_payload() -> None:
    payload = runtime_scale_payload(scale=1.2, line_height=1.8)
    assert payload == {"scale": 1.2, "line_height": 1.8}
