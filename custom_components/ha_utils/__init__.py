"""Home Assistant Utils — default theme font scaling action."""

from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.typing import ConfigType

from .const import INTEGRATION_VERSION
from .frontend_register import async_register_frontend, async_unregister_frontend
from .services import async_setup_services

PLATFORMS: list[str] = []


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Register services so actions appear in Developer tools."""
    async_setup_services(hass)
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Register frontend support for runtime font scaling."""
    await async_register_frontend(hass, INTEGRATION_VERSION)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload frontend support."""
    await async_unregister_frontend(hass)
    return True
