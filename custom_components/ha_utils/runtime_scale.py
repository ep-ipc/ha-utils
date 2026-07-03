"""Runtime font scale via frontend system storage."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from .const import SYSTEM_DATA_KEY

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant

_LOGGER = logging.getLogger(__name__)


def runtime_scale_payload(*, scale: float | int) -> dict[str, float]:
    """Build the value stored for the frontend module."""
    return {"scale": float(scale)}


async def async_set_font_scale(
    hass: HomeAssistant,
    *,
    scale: float | int,
) -> dict[str, Any]:
    """Persist scale for all browsers; the frontend module applies the CSS variable."""
    payload = runtime_scale_payload(scale=scale)

    from homeassistant.components.frontend.storage import async_system_store

    store = await async_system_store(hass)
    await store.async_set_item(SYSTEM_DATA_KEY, payload)
    _LOGGER.info("Set runtime font scale: scale=%s", scale)
    return payload
