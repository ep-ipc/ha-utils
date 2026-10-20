"""On/off weather signals published by HA Utils."""

from __future__ import annotations

from datetime import datetime

from homeassistant.components.binary_sensor import BinarySensorDeviceClass, BinarySensorEntity
from homeassistant.components.logbook import async_log_entry
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN, STORM_DEFAULT
from .device_meta import signal_device_info
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


def _iso(value: datetime | None) -> str | None:
    return None if value is None else value.isoformat()


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
        self._title = title
        self._attr_name = name
        self._attr_unique_id = f"{runtime.subentry_id}_{key}"
        self._attr_device_class = device_class
        if runtime.kind == "temperature":
            self._attr_device_info = signal_device_info(
                runtime.subentry_id, title, "Temperature", "temperature"
            )
        else:
            self._attr_device_info = signal_device_info(
                runtime.subentry_id, title, "Bad weather", "bad-weather"
            )

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        self._logged: bool | None = None

        @callback
        def _update() -> None:
            self.async_write_ha_state()
            # Log the Reason when this entity's own decision changes, not on every new number.
            if self._logged is not None and self.is_on != self._logged and self.runtime.reason:
                async_log_entry(self.hass, self._title, self.runtime.reason, DOMAIN, self.entity_id)
            self._logged = self.is_on

        self.async_on_remove(self.runtime.listen(_update))
        _update()

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
                "local_temperature": self.runtime.local_temperature,
                "forecast_temperature": self.runtime.forecast_temperature,
                "station_fresh": self.runtime.station_fresh,
                "hot_threshold": self.data_value("hot_threshold"),
                "cold_threshold": self.data_value("cold_threshold"),
                "clear_margin": self.runtime.margin(),
                "hot_expected_at": _iso(self.runtime.hot_at),
                "cold_expected_at": _iso(self.runtime.cold_at),
                "reason": self.runtime.reason,
            }
        return {
            "condition": self.runtime.condition,
            "local_bad": self.runtime.local_bad,
            "forecast_bad": self.runtime.forecast_bad,
            "station_fresh": self.runtime.station_fresh,
            "conditions": self.runtime.data.get("storm_conditions") or STORM_DEFAULT,
            "held_until": _iso(self.runtime.held_until),
            "next_bad_at": _iso(self.runtime.next_bad_at),
            "reason": self.runtime.reason,
        }

    def data_value(self, key: str):
        return self.runtime.data.get(key)
