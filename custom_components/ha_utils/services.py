"""Services for Home Assistant Utils."""

from __future__ import annotations

import logging

from homeassistant.core import HomeAssistant, ServiceCall, callback

from .const import DOMAIN
from .deploy import deploy_bundled_assets

_LOGGER = logging.getLogger(__name__)

SERVICE_DEPLOY_BUNDLED = "deploy_bundled"


@callback
def async_setup_services(hass: HomeAssistant) -> None:
    """Register HA Utils services."""

    async def handle_deploy_bundled(call: ServiceCall) -> None:
        result = await hass.async_add_executor_job(deploy_bundled_assets, hass)

        for rel in result.copied:
            _LOGGER.info("Deployed bundled resource: %s", rel)
        if result.skipped:
            _LOGGER.debug("Skipped %d existing bundled resource(s)", len(result.skipped))
        for err in result.errors:
            _LOGGER.error("%s", err)

    hass.services.async_register(
        DOMAIN,
        SERVICE_DEPLOY_BUNDLED,
        handle_deploy_bundled,
    )
