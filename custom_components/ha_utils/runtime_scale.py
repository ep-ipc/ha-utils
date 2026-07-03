"""Runtime typography scale via frontend system storage (default theme support)."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from .const import SYSTEM_DATA_KEY

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant

_LOGGER = logging.getLogger(__name__)


def runtime_scale_payload(
    *,
    scale: float | int,
    line_height: float | int,
) -> dict[str, float | int]:
    """Build the value stored for the frontend module."""
    return {"scale": scale, "line_height": line_height}


async def async_apply_runtime_scale(
    hass: HomeAssistant,
    *,
    scale: float | int,
    line_height: float | int,
    dry_run: bool,
) -> dict[str, Any] | None:
    """Persist scale for all browsers; the frontend module applies CSS variables."""
    payload = runtime_scale_payload(scale=scale, line_height=line_height)
    if dry_run:
        _LOGGER.info(
            "Would apply runtime font scale (default theme): scale=%s line_height=%s",
            scale,
            line_height,
        )
        return payload

    from homeassistant.components.frontend.storage import async_system_store

    store = await async_system_store(hass)
    await store.async_set_item(SYSTEM_DATA_KEY, payload)
    _LOGGER.info(
        "Applied runtime font scale: scale=%s line_height=%s",
        scale,
        line_height,
    )
    return payload
