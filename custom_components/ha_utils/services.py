"""Service actions for Home Assistant Utils."""

from __future__ import annotations

import voluptuous as vol

from homeassistant.core import HomeAssistant, ServiceCall, callback

from .const import (
    DEFAULT_FONT_SCALE,
    DOMAIN,
    MAX_FONT_SCALE,
    MIN_FONT_SCALE,
)
from .runtime_scale import async_set_font_scale

SERVICE_SET_FONT_SCALE = "set_font_scale"

SET_FONT_SCALE_SCHEMA = vol.Schema(
    {
        vol.Optional("scale", default=DEFAULT_FONT_SCALE): vol.All(
            vol.Coerce(float),
            vol.Range(min=MIN_FONT_SCALE, max=MAX_FONT_SCALE),
        ),
    }
)


@callback
def async_setup_services(hass: HomeAssistant) -> None:
    """Register HA Utils services."""

    async def handle_set_font_scale(call: ServiceCall) -> None:
        await async_set_font_scale(hass, scale=call.data["scale"])

    hass.services.async_register(
        DOMAIN,
        SERVICE_SET_FONT_SCALE,
        handle_set_font_scale,
        schema=SET_FONT_SCALE_SCHEMA,
    )
