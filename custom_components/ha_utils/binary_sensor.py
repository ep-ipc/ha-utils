"""On/off weather signals published by HA Utils."""

from __future__ import annotations

from homeassistant.components.binary_sensor import BinarySensorDeviceClass, BinarySensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .signals_runtime import ThresholdRuntime

_RUNTIMES = "threshold_runtimes"


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Create one binary sensor for each hot, cold, or storm subentry."""

    runtimes: dict[str, ThresholdRuntime] = hass.data.setdefault(DOMAIN, {}).setdefault(_RUNTIMES, {})
    models = {
        "hot_day": ("Hot day", BinarySensorDeviceClass.HEAT),
        "cold_day": ("Cold day", BinarySensorDeviceClass.COLD),
        "thunderstorm": ("Thunderstorm", None),
    }
    for subentry in entry.subentries.values():
        if subentry.subentry_type not in models:
            continue
        runtime = runtimes.get(subentry.subentry_id)
        if runtime is None:
            runtime = ThresholdRuntime(
                hass, subentry.subentry_id, dict(subentry.data), subentry.subentry_type
            )
            runtimes[subentry.subentry_id] = runtime
            entry.async_on_unload(runtime.async_start())
        model, device_class = models[subentry.subentry_type]
        async_add_entities(
            [ThresholdBinarySensor(runtime, subentry.title, model, device_class)],
            config_subentry_id=subentry.subentry_id,
        )


class ThresholdBinarySensor(BinarySensorEntity):
    _attr_has_entity_name = True
    _attr_should_poll = False
    _attr_name = "Active"

    def __init__(
        self,
        runtime: ThresholdRuntime,
        title: str,
        model: str,
        device_class: BinarySensorDeviceClass | None,
    ) -> None:
        self.runtime = runtime
        self._attr_unique_id = f"{runtime.subentry_id}_active"
        self._attr_device_class = device_class
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, runtime.subentry_id)},
            name=title,
            manufacturer="HA Utils",
            model=model,
        )

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        self.async_on_remove(self.runtime.listen(self.async_write_ha_state))

    @property
    def is_on(self) -> bool:
        return self.runtime.is_on
