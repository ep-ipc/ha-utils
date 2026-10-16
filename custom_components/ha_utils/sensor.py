"""Sensors published by HA Utils signal entries."""

from __future__ import annotations

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity, SensorStateClass
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .signals_runtime import ThresholdRuntime, WindSignalRuntime, async_get_threshold_runtime

_RUNTIMES = "runtimes"


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Create sensors for each wind signal subentry."""

    runtimes: dict[str, WindSignalRuntime] = hass.data.setdefault(DOMAIN, {}).setdefault(_RUNTIMES, {})
    for subentry in entry.subentries.values():
        if subentry.subentry_type != "wind_signal":
            continue
        runtime = runtimes.get(subentry.subentry_id)
        if runtime is None:
            runtime = WindSignalRuntime(hass, subentry.subentry_id, dict(subentry.data))
            runtimes[subentry.subentry_id] = runtime
            entry.async_on_unload(runtime.async_start())
        async_add_entities(
            [
                WindLevelSensor(runtime, subentry.title),
                WindNumberSensor(runtime, subentry.title, "risk", "Risk", SensorDeviceClass.WIND_SPEED),
                WindNumberSensor(runtime, subentry.title, "calm", "Calm", SensorDeviceClass.WIND_SPEED),
                WindNumberSensor(runtime, subentry.title, "factor", "Gust factor", None),
            ],
            config_subentry_id=subentry.subentry_id,
        )
    for subentry in entry.subentries.values():
        if subentry.subentry_type == "temperature":
            runtime = async_get_threshold_runtime(
                hass, entry, subentry.subentry_id, dict(subentry.data), "temperature"
            )
            async_add_entities(
                [TemperatureReadingSensor(runtime, subentry.title)],
                config_subentry_id=subentry.subentry_id,
            )
        elif subentry.subentry_type == "bad_weather":
            runtime = async_get_threshold_runtime(
                hass, entry, subentry.subentry_id, dict(subentry.data), "bad_weather"
            )
            async_add_entities(
                [WeatherConditionSensor(runtime, subentry.title)],
                config_subentry_id=subentry.subentry_id,
            )


def _device(subentry_id: str, title: str, model: str) -> DeviceInfo:
    return DeviceInfo(
        identifiers={(DOMAIN, subentry_id)},
        name=title,
        manufacturer="HA Utils",
        model=model,
    )


class _WindSensor(SensorEntity):
    _attr_has_entity_name = True
    _attr_should_poll = False

    def __init__(self, runtime: WindSignalRuntime, title: str, key: str, name: str) -> None:
        self.runtime = runtime
        self._attr_name = name
        self._attr_unique_id = f"{runtime.subentry_id}_{key}"
        self._attr_device_info = _device(runtime.subentry_id, title, "Wind")

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        self.async_on_remove(self.runtime.listen(self.async_write_ha_state))

    @property
    def extra_state_attributes(self) -> dict:
        snap = self.runtime.engine.snapshot
        return {
            "gust_3m": snap.gust_3m,
            "gust_30m": snap.gust_30m,
            "forecast_1h": snap.forecast_1h,
            "forecast_2h": snap.forecast_2h,
            "factor_sample": snap.sample,
            "forecast_fresh": snap.forecast_fresh,
            "station_fresh": snap.station_fresh,
        }


class WindLevelSensor(_WindSensor):
    def __init__(self, runtime: WindSignalRuntime, title: str) -> None:
        super().__init__(runtime, title, "level", "Level")

    @property
    def native_value(self) -> str:
        return self.runtime.engine.snapshot.level


class WindNumberSensor(_WindSensor):
    def __init__(
        self,
        runtime: WindSignalRuntime,
        title: str,
        key: str,
        name: str,
        device_class: SensorDeviceClass | None,
    ) -> None:
        super().__init__(runtime, title, key, name)
        self._key = key
        self._attr_device_class = device_class
        if device_class == SensorDeviceClass.WIND_SPEED:
            self._attr_state_class = SensorStateClass.MEASUREMENT
            self._attr_native_unit_of_measurement = runtime.unit
        else:
            self._attr_suggested_display_precision = 2

    @property
    def native_value(self) -> float | None:
        snap = self.runtime.engine.snapshot
        if self._key == "risk":
            return snap.risk
        if self._key == "calm":
            return snap.calm
        return snap.factor


class TemperatureReadingSensor(SensorEntity):
    _attr_has_entity_name = True
    _attr_should_poll = False
    _attr_name = "Temperature"
    _attr_device_class = SensorDeviceClass.TEMPERATURE
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(self, runtime: ThresholdRuntime, title: str) -> None:
        self.runtime = runtime
        self._attr_unique_id = f"{runtime.subentry_id}_temperature"
        self._attr_device_info = _device(runtime.subentry_id, title, "Temperature")

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        self.async_on_remove(self.runtime.listen(self.async_write_ha_state))

    @property
    def native_value(self) -> float | None:
        return self.runtime.temperature

    @property
    def extra_state_attributes(self) -> dict:
        return {
            "local_temperature": self.runtime.local_temperature,
            "forecast_temperature": self.runtime.forecast_temperature,
            "station_fresh": self.runtime.station_fresh,
            "hot_threshold": self.runtime.data.get("hot_threshold", 90),
            "cold_threshold": self.runtime.data.get("cold_threshold", 32),
        }

    @property
    def native_unit_of_measurement(self) -> str | None:
        state = self.hass.states.get(self.runtime.data["weather_entity"])
        if state is None:
            return None
        unit = state.attributes.get("temperature_unit")
        return str(unit) if unit else None


class WeatherConditionSensor(SensorEntity):
    _attr_has_entity_name = True
    _attr_should_poll = False
    _attr_name = "Condition"
    _attr_icon = "mdi:weather-lightning-rainy"

    def __init__(self, runtime: ThresholdRuntime, title: str) -> None:
        self.runtime = runtime
        self._attr_unique_id = f"{runtime.subentry_id}_condition"
        self._attr_device_info = _device(runtime.subentry_id, title, "Bad weather")

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        self.async_on_remove(self.runtime.listen(self.async_write_ha_state))

    @property
    def native_value(self) -> str | None:
        return self.runtime.condition

    @property
    def extra_state_attributes(self) -> dict:
        return {
            "local_bad": self.runtime.local_bad,
            "forecast_bad": self.runtime.forecast_bad,
            "station_fresh": self.runtime.station_fresh,
        }
