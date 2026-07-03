"""Register the runtime font-scale frontend module."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import TYPE_CHECKING

from homeassistant.components.frontend import add_extra_js_url
from homeassistant.components.http import StaticPathConfig

from .const import DOMAIN

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant

_LOGGER = logging.getLogger(__name__)

DATA_FRONTEND_REGISTERED = "frontend_registered"
DATA_FRONTEND_JS_URL = "frontend_js_url"
FRONTEND_STATIC = f"/{DOMAIN}/frontend"
JS_PATH = f"{FRONTEND_STATIC}/font-scale.js"


async def async_register_frontend(hass: HomeAssistant, version: str) -> None:
    """Serve font-scale.js and load it on every HA frontend page."""
    domain_data = hass.data.setdefault(DOMAIN, {})
    if domain_data.get(DATA_FRONTEND_REGISTERED):
        return

    frontend_dir = Path(__file__).resolve().parent / "frontend"
    if not frontend_dir.is_dir():
        _LOGGER.error("Frontend assets not found: %s", frontend_dir)
        return

    try:
        await hass.http.async_register_static_paths(
            [StaticPathConfig(FRONTEND_STATIC, str(frontend_dir))]
        )
    except Exception:  # noqa: BLE001 — path may already be registered after reload
        _LOGGER.debug("Static path %s already registered", FRONTEND_STATIC)

    js_url = f"{JS_PATH}?v={version}"
    add_extra_js_url(hass, js_url)

    domain_data[DATA_FRONTEND_REGISTERED] = True
    domain_data[DATA_FRONTEND_JS_URL] = js_url
    _LOGGER.debug("Registered runtime font-scale frontend module")


async def async_unregister_frontend(hass: HomeAssistant) -> None:
    """Remove the frontend module on integration unload."""
    domain_data = hass.data.get(DOMAIN, {})
    if not domain_data.pop(DATA_FRONTEND_REGISTERED, False):
        return

    js_url = domain_data.pop(DATA_FRONTEND_JS_URL, JS_PATH)
    try:
        from homeassistant.components.frontend import remove_extra_js_url

        remove_extra_js_url(hass, js_url)
    except (ImportError, KeyError, ValueError):
        _LOGGER.debug("Could not remove extra JS URL %s (already gone?)", js_url)
