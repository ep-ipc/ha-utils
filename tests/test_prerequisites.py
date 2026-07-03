"""Tests for configuration prerequisite checks."""

from __future__ import annotations

from conftest import load_ha_utils_module

prerequisites = load_ha_utils_module("prerequisites")
_packages_enabled_in_config = prerequisites._packages_enabled_in_config


def test_packages_enabled_include_dir_named() -> None:
    text = """
homeassistant:
  name: Home
  packages: !include_dir_named packages
"""
    assert _packages_enabled_in_config(text) is True


def test_packages_not_enabled() -> None:
    text = """
homeassistant:
  name: Home
"""
    assert _packages_enabled_in_config(text) is False


def test_packages_inline() -> None:
    text = """
homeassistant:
  packages:
    foo: !include foo.yaml
"""
    assert _packages_enabled_in_config(text) is True
