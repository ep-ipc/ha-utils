"""Service actions for Home Assistant Utils."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import TYPE_CHECKING

import voluptuous as vol

from homeassistant.core import HomeAssistant, ServiceCall, callback
from homeassistant.helpers import config_validation as cv

from .const import (
    DEFAULT_FONT_SCALE,
    DEFAULT_LINE_HEIGHT,
    DOMAIN,
    MAX_FONT_SCALE,
    MIN_FONT_SCALE,
)
from .deploy import deploy_bundled_assets
from .theme_patcher import patch_all_themes

if TYPE_CHECKING:
    from .deploy import DeployResult

_LOGGER = logging.getLogger(__name__)

SERVICE_PATCH_THEMES = "patch_themes"
SERVICE_RELOAD_THEMES = "reload_themes"
SERVICE_DEPLOY_BUNDLED = "deploy_bundled"

PATCH_THEMES_SCHEMA = vol.Schema(
    {
        vol.Optional("scale", default=DEFAULT_FONT_SCALE): vol.All(
            vol.Coerce(float),
            vol.Range(min=MIN_FONT_SCALE, max=MAX_FONT_SCALE),
        ),
        vol.Optional("line_height", default=DEFAULT_LINE_HEIGHT): vol.All(
            vol.Coerce(float),
            vol.Range(min=1.0, max=3.0),
        ),
        vol.Optional("dry_run", default=False): cv.boolean,
    }
)


def _log_patch_result(result: object, *, dry_run: bool) -> None:
    from .theme_patcher import PatchResult

    if not isinstance(result, PatchResult):
        return

    if result.errors:
        for err in result.errors:
            _LOGGER.error("%s", err)

    if dry_run:
        for path in result.would_change:
            _LOGGER.info("Would patch theme: %s", path)
        if not result.would_change and not result.errors:
            _LOGGER.info("No theme files would change")
        return

    for path in result.changed:
        _LOGGER.info("Patched theme: %s", path)
    if not result.changed and not result.errors:
        _LOGGER.info("All theme files already match target typography")


@callback
def async_setup_services(hass: HomeAssistant) -> None:
    """Register HA Utils services."""

    async def handle_patch_themes(call: ServiceCall) -> None:
        themes_dir = Path(hass.config.path("themes"))
        scale = call.data["scale"]
        line_height = call.data["line_height"]
        dry_run = call.data["dry_run"]

        result = await hass.async_add_executor_job(
            patch_all_themes,
            themes_dir,
            scale=scale,
            line_height=line_height,
            dry_run=dry_run,
        )
        _log_patch_result(result, dry_run=dry_run)

    async def handle_reload_themes(call: ServiceCall) -> None:
        await hass.services.async_call(
            "frontend",
            "reload_themes",
            blocking=True,
        )
        _LOGGER.info("Reloaded themes")

    async def handle_deploy_bundled(call: ServiceCall) -> None:
        result: DeployResult = await hass.async_add_executor_job(
            deploy_bundled_assets, hass
        )
        if result.copied:
            for rel in result.copied:
                _LOGGER.info("Deployed: %s", rel)
        if result.skipped:
            _LOGGER.debug("Skipped existing files: %d", len(result.skipped))
        for err in result.errors:
            _LOGGER.error("%s", err)

        from .repairs import async_update_repairs

        await async_update_repairs(hass, deploy_result=result)

    hass.services.async_register(
        DOMAIN,
        SERVICE_PATCH_THEMES,
        handle_patch_themes,
        schema=PATCH_THEMES_SCHEMA,
    )
    hass.services.async_register(
        DOMAIN,
        SERVICE_RELOAD_THEMES,
        handle_reload_themes,
    )
    hass.services.async_register(
        DOMAIN,
        SERVICE_DEPLOY_BUNDLED,
        handle_deploy_bundled,
    )
