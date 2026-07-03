"""Home Assistant Utils integration."""

from __future__ import annotations

import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.typing import ConfigType

from .deploy import deploy_bundled_assets
from .services import async_setup_services

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[str] = []


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Register integration services."""
    async_setup_services(hass)
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Deploy bundled resources when the integration is set up."""
    result = await hass.async_add_executor_job(deploy_bundled_assets, hass)

    if result.copied:
        _LOGGER.info(
            "Deployed %d bundled resource(s): %s",
            len(result.copied),
            ", ".join(result.copied),
        )
    if result.skipped:
        _LOGGER.debug("Skipped %d existing bundled resource(s)", len(result.skipped))
    for err in result.errors:
        _LOGGER.error("%s", err)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload Home Assistant Utils."""
    return True
