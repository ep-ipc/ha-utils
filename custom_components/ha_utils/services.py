"""Services for Home Assistant Utils."""

from __future__ import annotations

import logging
from functools import partial

import voluptuous as vol

from homeassistant.core import HomeAssistant, ServiceCall, callback
from homeassistant.helpers import config_validation as cv

from .const import DOMAIN
from .deploy import deploy_bundled_assets
from .voice import (
    DEFAULT_ASSISTANTS,
    KNOWN_ASSISTANTS,
    expose_entities_to_voice_assistants,
)

_LOGGER = logging.getLogger(__name__)

SERVICE_DEPLOY_BUNDLED = "deploy_bundled"
SERVICE_EXPOSE_ENTITIES = "expose_entities_to_voice_assistant"

DEPLOY_BUNDLED_SCHEMA = vol.Schema(
    {
        vol.Optional("overwrite_existing", default=True): cv.boolean,
        vol.Optional("backup_existing", default=True): cv.boolean,
    }
)

EXPOSE_ENTITIES_SCHEMA = vol.Schema(
    {
        vol.Optional("entity_ids", default=[]): cv.entity_ids,
        vol.Optional("assistants", default=list(DEFAULT_ASSISTANTS)): vol.All(
            cv.ensure_list,
            [vol.In(KNOWN_ASSISTANTS)],
        ),
    }
)


@callback
def async_setup_services(hass: HomeAssistant) -> None:
    """Register HA Utils services."""

    async def handle_deploy_bundled(call: ServiceCall) -> None:
        result = await hass.async_add_executor_job(
            partial(
                deploy_bundled_assets,
                hass,
                overwrite_existing=call.data["overwrite_existing"],
                backup_existing=call.data["backup_existing"],
            )
        )

        for rel in result.copied:
            _LOGGER.info("Deployed bundled resource: %s", rel)
        for rel in result.updated:
            _LOGGER.info("Updated bundled resource: %s", rel)
        for rel in result.backed_up:
            _LOGGER.info("Backed up existing bundled resource: %s", rel)
        if result.skipped:
            _LOGGER.debug(
                "Skipped %d existing bundled resource(s)",
                len(result.skipped),
            )
        for err in result.errors:
            _LOGGER.error("%s", err)

    async def handle_expose_entities(call: ServiceCall) -> None:
        result = expose_entities_to_voice_assistants(
            hass,
            entity_ids=call.data["entity_ids"],
            assistants=call.data["assistants"],
        )

        for err in result.errors:
            _LOGGER.error("%s", err)
        _LOGGER.info(
            "Exposed %d entity/entities to voice assistant(s); skipped %d already exposed",
            len(result.exposed),
            len(result.skipped_already_exposed),
        )

    hass.services.async_register(
        DOMAIN,
        SERVICE_DEPLOY_BUNDLED,
        handle_deploy_bundled,
        schema=DEPLOY_BUNDLED_SCHEMA,
    )
    hass.services.async_register(
        DOMAIN,
        SERVICE_EXPOSE_ENTITIES,
        handle_expose_entities,
        schema=EXPOSE_ENTITIES_SCHEMA,
    )
