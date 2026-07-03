"""Discover Home Assistant theme YAML file locations from configuration."""

from __future__ import annotations

import re
from pathlib import Path

_INCLUDE_DIR_MERGE = re.compile(
    r"^\s*themes\s*:\s*!include_dir_merge_named\s+(\S+)",
    re.MULTILINE,
)
_INCLUDE_DIR_NAMED = re.compile(
    r"^\s*themes\s*:\s*!include_dir_named\s+(\S+)",
    re.MULTILINE,
)
_INCLUDE_FILE = re.compile(
    r"^\s*themes\s*:\s*!include\s+(\S+)",
    re.MULTILINE,
)

_COMMON_THEME_DIRS = (
    "themes",
    "theme",
    "custom/themes",
    "themes/custom",
)

THEMES_SETUP_HINT = (
    "Optional: add theme YAML for Mushroom/card-mod deep customization:\n"
    "  1. Create a themes/ folder in your config directory\n"
    "  2. Add to configuration.yaml:\n"
    "       frontend:\n"
    "         themes: !include_dir_merge_named themes\n"
    "  3. Install themes (HACS or copy .yaml files into themes/)\n"
    "Runtime font scaling works without this — it applies to the default HA theme."
)


def _normalize_include_path(raw: str) -> str:
    return raw.strip().strip("'\"").rstrip("/")


def _safe_config_path(config_dir: Path, relative: str) -> Path | None:
    """Resolve a config-relative path; reject escapes outside config_dir."""
    candidate = (config_dir / relative).resolve()
    try:
        candidate.relative_to(config_dir.resolve())
    except ValueError:
        return None
    return candidate


def discover_theme_sources(
    config_dir: Path,
    configuration_text: str | None,
) -> list[Path]:
    """Return theme directories or single YAML files referenced by configuration."""
    sources: list[Path] = []
    seen: set[Path] = set()

    def _add(candidate: Path | None) -> None:
        if candidate is None or candidate in seen:
            return
        if candidate.is_file() or candidate.is_dir():
            seen.add(candidate)
            sources.append(candidate)

    if configuration_text:
        for pattern in (_INCLUDE_DIR_MERGE, _INCLUDE_DIR_NAMED, _INCLUDE_FILE):
            for match in pattern.finditer(configuration_text):
                rel = _normalize_include_path(match.group(1))
                _add(_safe_config_path(config_dir, rel))

    for name in _COMMON_THEME_DIRS:
        _add(_safe_config_path(config_dir, name))

    return sources


def read_configuration_text(config_dir: Path) -> str | None:
    """Read configuration.yaml if present."""
    config_path = config_dir / "configuration.yaml"
    if not config_path.is_file():
        return None
    return config_path.read_text(encoding="utf-8")
