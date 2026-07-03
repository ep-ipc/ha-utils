"""Read-only checks for Home Assistant configuration prerequisites."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

from .const import PACKAGE_REL_PATH

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant

_PACKAGES_LINE = re.compile(
    r"^\s*packages\s*:",
    re.MULTILINE,
)
_HASS_BLOCK = re.compile(
    r"(?ms)^homeassistant\s*:\s*\n(.*?)(?=^\S|\Z)",
)


@dataclass
class PrerequisiteStatus:
    """Result of prerequisite checks."""

    packages_enabled: bool
    package_file_present: bool
    configuration_readable: bool


def check_prerequisites(hass: HomeAssistant) -> PrerequisiteStatus:
    """Check whether packages are enabled and the HA Utils package file exists."""
    config_dir = Path(hass.config.config_dir)
    package_path = config_dir / PACKAGE_REL_PATH
    package_file_present = package_path.is_file()

    configuration_path = config_dir / "configuration.yaml"
    if not configuration_path.is_file():
        return PrerequisiteStatus(
            packages_enabled=False,
            package_file_present=package_file_present,
            configuration_readable=False,
        )

    try:
        text = configuration_path.read_text(encoding="utf-8")
    except OSError:
        return PrerequisiteStatus(
            packages_enabled=False,
            package_file_present=package_file_present,
            configuration_readable=False,
        )

    packages_enabled = _packages_enabled_in_config(text)
    return PrerequisiteStatus(
        packages_enabled=packages_enabled,
        package_file_present=package_file_present,
        configuration_readable=True,
    )


def _packages_enabled_in_config(text: str) -> bool:
    if _PACKAGES_LINE.search(text):
        return True

    for match in _HASS_BLOCK.finditer(text):
        block = match.group(1)
        if _PACKAGES_LINE.search(block):
            return True

    return False
