"""Diagnostics download for HA Utils signal entries."""

from __future__ import annotations

from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .const import DOMAIN
from .signals_runtime import THRESHOLD_RUNTIMES, WIND_RUNTIMES


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: ConfigEntry
) -> dict[str, Any]:
    """Each signal's settings, sources, and the numbers behind its current state."""

    data = hass.data.get(DOMAIN, {})
    runtimes = {**data.get(WIND_RUNTIMES, {}), **data.get(THRESHOLD_RUNTIMES, {})}
    signals = {}
    for subentry in entry.subentries.values():
        runtime = runtimes.get(subentry.subentry_id)
        signals[subentry.subentry_id] = {
            "title": subentry.title,
            "type": subentry.subentry_type,
            "runtime": None if runtime is None else runtime.diagnostics(),
        }
    return {"signals": signals}
