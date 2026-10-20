"""Device triggers for HA Utils signal devices."""

from __future__ import annotations

import voluptuous as vol

from homeassistant.components.device_automation import DEVICE_TRIGGER_BASE_SCHEMA
from homeassistant.components.homeassistant.triggers import state as state_trigger
from homeassistant.const import (
    CONF_DEVICE_ID,
    CONF_DOMAIN,
    CONF_ENTITY_ID,
    CONF_PLATFORM,
    CONF_TYPE,
)
from homeassistant.core import CALLBACK_TYPE, HomeAssistant
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.trigger import TriggerActionType, TriggerInfo
from homeassistant.helpers.typing import ConfigType

from .const import DOMAIN

# Trigger type → (unique_id suffix of the entity it watches, state it moves to).
TRIGGERS = {
    "level_safe": ("level", "safe"),
    "level_advisory": ("level", "advisory"),
    "level_warning": ("level", "warning"),
    "hot_on": ("hot", "on"),
    "hot_off": ("hot", "off"),
    "cold_on": ("cold", "on"),
    "cold_off": ("cold", "off"),
    "bad_weather_on": ("active", "on"),
    "bad_weather_off": ("active", "off"),
}

TRIGGER_SCHEMA = DEVICE_TRIGGER_BASE_SCHEMA.extend(
    {
        vol.Required(CONF_ENTITY_ID): cv.entity_id_or_uuid,
        vol.Required(CONF_TYPE): vol.In(TRIGGERS),
    }
)


async def async_get_triggers(hass: HomeAssistant, device_id: str) -> list[dict[str, str]]:
    """Level, Hot, Cold, and Bad weather changes offered on the device page."""

    device = dr.async_get(hass).async_get(device_id)
    if device is None:
        return []
    subentry_ids = {value for domain, value in device.identifiers if domain == DOMAIN}
    triggers = []
    for entry in er.async_entries_for_device(er.async_get(hass), device_id):
        if entry.platform != DOMAIN:
            continue
        for subentry_id in subentry_ids:
            prefix = f"{subentry_id}_"
            if not entry.unique_id.startswith(prefix):
                continue
            suffix = entry.unique_id[len(prefix):]
            for trigger_type, (key, _to) in TRIGGERS.items():
                if key == suffix:
                    triggers.append(
                        {
                            CONF_PLATFORM: "device",
                            CONF_DEVICE_ID: device_id,
                            CONF_DOMAIN: DOMAIN,
                            CONF_ENTITY_ID: entry.id,
                            CONF_TYPE: trigger_type,
                        }
                    )
    return triggers


async def async_attach_trigger(
    hass: HomeAssistant,
    config: ConfigType,
    action: TriggerActionType,
    trigger_info: TriggerInfo,
) -> CALLBACK_TYPE:
    """Attach a state trigger on the signal entity."""

    _key, to_state = TRIGGERS[config[CONF_TYPE]]
    state_config = await state_trigger.async_validate_trigger_config(
        hass,
        {
            CONF_PLATFORM: "state",
            CONF_ENTITY_ID: config[CONF_ENTITY_ID],
            state_trigger.CONF_TO: to_state,
        },
    )
    return await state_trigger.async_attach_trigger(
        hass, state_config, action, trigger_info, platform_type="device"
    )
