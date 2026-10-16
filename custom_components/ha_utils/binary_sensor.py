"""On/off weather signals published by HA Utils."""

from __future__ import annotations

from homeassistant.components.binary_sensor import BinarySensorDeviceClass, BinarySensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .signals_runtime import ThresholdRuntime, async_get_threshold_runtime


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Create binary sensors for temperature and bad-weather entries."""

    for subentry in entry.subentries.values():
        if subentry.subentry_type == "temperature":
            runtime = async_get_threshold_runtime(
                hass, entry, subentry.subentry_id, dict(subentry.data), "temperature"
            )
            async_add_entities(
                [
                    ThresholdBinarySensor(runtime, subentry.title, "Hot", "hot", BinarySensorDeviceClass.HEAT),
                    ThresholdBinarySensor(runtime, subentry.title, "Cold", "cold", BinarySensorDeviceClass.COLD),
                ],
                config_subentry_id=subentry.subentry_id,
            )
        elif subentry.subentry_type == "bad_weather":
            runtime = async_get_threshold_runtime(
                hass, entry, subentry.subentry_id, dict(subentry.data), "bad_weather"
            )
            async_add_entities(
                [ThresholdBinarySensor(runtime, subentry.title, "Bad weather", "active", None)],
                config_subentry_id=subentry.subentry_id,
            )


class ThresholdBinarySensor(BinarySensorEntity):
    _attr_has_entity_name = True
    _attr_should_poll = False

    def __init__(
        self,
        runtime: ThresholdRuntime,
        title: str,
        name: str,
        key: str,
        device_class: BinarySensorDeviceClass | None,
    ) -> None:
        self.runtime = runtime
        self._key = key
        self._attr_name = name
        self._attr_unique_id = f"{runtime.subentry_id}_{key}"
        self._attr_device_class = device_class
        model = "Temperature" if runtime.kind == "temperature" else "Bad weather"
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
        if self._key == "hot":
            return self.runtime.hot
        if self._key == "cold":
            return self.runtime.cold
        return self.runtime.is_on

    @property
    def extra_state_attributes(self) -> dict:
        if self.runtime.kind == "temperature":
            return {
                "temperature": self.runtime.temperature,
                "hot_threshold": self.data_value("hot_threshold"),
                "cold_threshold": self.data_value("cold_threshold"),
            }
        return {
            "condition": self.runtime.condition,
            "conditions": self.runtime.data.get("storm_conditions"),
        }

    def data_value(self, key: str):
        return self.runtime.data.get(key)
