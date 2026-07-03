"""Home Assistant Utils — bundled packages, blueprints, and utility actions."""

from __future__ import annotations

import logging
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.typing import ConfigType

from .const import DOMAIN
from .deploy import deploy_bundled_assets
from .repairs import async_clear_repairs, async_update_repairs
from .services import async_setup_services

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[str] = []


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Register services so actions appear in Developer tools."""
    async_setup_services(hass)
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Deploy bundled assets and sync repair issues."""
    deploy_result = await hass.async_add_executor_job(deploy_bundled_assets, hass)
    if deploy_result.copied:
        _LOGGER.info(
            "Deployed %d bundled file(s): %s",
            len(deploy_result.copied),
            ", ".join(deploy_result.copied),
        )
    for err in deploy_result.errors:
        _LOGGER.error("%s", err)

    await async_update_repairs(hass, deploy_result=deploy_result)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Clear repair issues on unload."""
    await async_clear_repairs(hass)
    return True
