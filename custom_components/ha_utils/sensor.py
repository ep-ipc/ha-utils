"""Sensors published by HA Utils signal entries."""

from __future__ import annotations

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity, SensorStateClass
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN, DOCS_DEVICES
from .device_meta import signal_device_info
from .signals_runtime import ThresholdRuntime, WindSignalRuntime, async_get_threshold_runtime

_RUNTIMES = "runtimes"


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Create sensors for each signal subentry."""

    runtimes: dict[str, WindSignalRuntime] = hass.data.setdefault(DOMAIN, {}).setdefault(
        _RUNTIMES, {}
    )
    for subentry in entry.subentries.values():
        if subentry.subentry_type != "wind_signal":
            continue
        runtime = runtimes.get(subentry.subentry_id)
        if runtime is None:
            runtime = WindSignalRuntime(hass, subentry.subentry_id, dict(subentry.data))
            runtimes[subentry.subentry_id] = runtime
            entry.async_on_unload(runtime.async_start())

            def _drop(subentry_id: str = subentry.subentry_id) -> None:
                runtimes.pop(subentry_id, None)

            entry.async_on_unload(_drop)
        async_add_entities(
            [
                WindLevelSensor(runtime, subentry.title),
                WindNumberSensor(runtime, subentry.title, "risk", "Risk", SensorDeviceClass.WIND_SPEED),
                WindNumberSensor(runtime, subentry.title, "calm", "Calm", SensorDeviceClass.WIND_SPEED),
                WindNumberSensor(runtime, subentry.title, "factor", "Gust factor", None),
                WindGuideSensor(runtime, subentry.title),
            ],
            config_subentry_id=subentry.subentry_id,
        )
    for subentry in entry.subentries.values():
        if subentry.subentry_type == "temperature":
            runtime = async_get_threshold_runtime(
                hass, entry, subentry.subentry_id, dict(subentry.data), "temperature"
            )
            async_add_entities(
                [
                    TemperatureReadingSensor(runtime, subentry.title),
                    TemperatureGuideSensor(runtime, subentry.title),
                ],
                config_subentry_id=subentry.subentry_id,
            )
        elif subentry.subentry_type == "bad_weather":
            runtime = async_get_threshold_runtime(
                hass, entry, subentry.subentry_id, dict(subentry.data), "bad_weather"
            )
            async_add_entities(
                [
                    WeatherConditionSensor(runtime, subentry.title),
                    WeatherReasonSensor(runtime, subentry.title),
                    BadWeatherGuideSensor(runtime, subentry.title),
                ],
                config_subentry_id=subentry.subentry_id,
            )


def _line(data: dict, key: str, default: float) -> float:
    value = data.get(key, default)
    return float(value) if isinstance(value, (int, float)) else default


class _WindSensor(SensorEntity):
    _attr_has_entity_name = True
    _attr_should_poll = False

    def __init__(self, runtime: WindSignalRuntime, title: str, key: str, name: str) -> None:
        self.runtime = runtime
        self._attr_name = name
        self._attr_unique_id = f"{runtime.subentry_id}_{key}"
        self._attr_device_info = signal_device_info(runtime.subentry_id, title, "Wind", "wind")

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


class WindGuideSensor(SensorEntity):
    """How to use Wind, shown on the device diagnostics card."""

    _attr_has_entity_name = True
    _attr_should_poll = False
    _attr_name = "Guide"
    _attr_icon = "mdi:information-outline"
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(self, runtime: WindSignalRuntime, title: str) -> None:
        self.runtime = runtime
        self._attr_unique_id = f"{runtime.subentry_id}_guide"
        self._attr_device_info = signal_device_info(runtime.subentry_id, title, "Wind", "wind")

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        self.async_on_remove(self.runtime.listen(self.async_write_ha_state))

    def _lines(self) -> tuple[float, float, float, float, str]:
        data = self.runtime.data
        unit = self.runtime.unit
        return (
            _line(data, "rise_big", 30),
            _line(data, "rise_all", 60),
            _line(data, "fall_all", 45),
            _line(data, "fall_big", 20),
            unit,
        )

    @property
    def native_value(self) -> str:
        advisory, warning, fall_warning, fall_safe, unit = self._lines()
        return (
            f"↑ safe → advisory ({advisory:g} {unit}) → warning ({warning:g} {unit}) · "
            f"↓ warning → advisory (<{fall_warning:g} {unit}) → safe (<{fall_safe:g} {unit})"
        )

    @property
    def extra_state_attributes(self) -> dict:
        advisory, warning, fall_warning, fall_safe, unit = self._lines()
        return {
            "how_to_use": (
                "Watch Level in your own automation. "
                "Risk raises the latch; Calm lowers it. "
                "Set Weather station, Forecast, and the four speeds under Configuration. "
                "Missing Risk or Calm never counts as calm."
            ),
            "rise": (
                f"safe → advisory when Risk ≥ {advisory:g} {unit} → "
                f"warning when Risk ≥ {warning:g} {unit}"
            ),
            "fall": (
                f"warning → advisory when Calm < {fall_warning:g} {unit} → "
                f"safe when Calm < {fall_safe:g} {unit}"
            ),
            "rise_to_advisory": (
                f"When Risk reaches {advisory:g} {unit}, Level becomes advisory."
            ),
            "rise_to_warning": (
                f"When Risk reaches {warning:g} {unit}, Level becomes warning."
            ),
            "fall_from_warning": (
                f"When Calm falls below {fall_warning:g} {unit}, Level leaves warning for advisory."
            ),
            "fall_to_safe": (
                f"When Calm falls below {fall_safe:g} {unit}, Level becomes safe."
            ),
            "docs": f"{DOCS_DEVICES}/wind.md",
        }


class TemperatureReadingSensor(SensorEntity):
    _attr_has_entity_name = True
    _attr_should_poll = False
    _attr_name = "Temperature"
    _attr_device_class = SensorDeviceClass.TEMPERATURE
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(self, runtime: ThresholdRuntime, title: str) -> None:
        self.runtime = runtime
        self._attr_unique_id = f"{runtime.subentry_id}_temperature"
        self._attr_device_info = signal_device_info(
            runtime.subentry_id, title, "Temperature", "temperature"
        )

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


class TemperatureGuideSensor(SensorEntity):
    _attr_has_entity_name = True
    _attr_should_poll = False
    _attr_name = "Guide"
    _attr_icon = "mdi:information-outline"
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(self, runtime: ThresholdRuntime, title: str) -> None:
        self.runtime = runtime
        self._attr_unique_id = f"{runtime.subentry_id}_guide"
        self._attr_device_info = signal_device_info(
            runtime.subentry_id, title, "Temperature", "temperature"
        )

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        self.async_on_remove(self.runtime.listen(self.async_write_ha_state))

    @property
    def native_value(self) -> str:
        hot = _line(self.runtime.data, "hot_threshold", 90)
        cold = _line(self.runtime.data, "cold_threshold", 32)
        return f"Cold below {cold:g} · Hot above {hot:g}"

    @property
    def extra_state_attributes(self) -> dict:
        hot = _line(self.runtime.data, "hot_threshold", 90)
        cold = _line(self.runtime.data, "cold_threshold", 32)
        return {
            "summary": (
                "Live station temperature is preferred when fresh. "
                "Forecast high/low next 2 hours can turn Hot or Cold on early."
            ),
            "hot_above": f"Hot turns on above {hot:g}.",
            "cold_below": f"Cold turns on below {cold:g}.",
            "docs": f"{DOCS_DEVICES}/temperature.md",
        }


class WeatherConditionSensor(SensorEntity):
    _attr_has_entity_name = True
    _attr_should_poll = False
    _attr_name = "Condition"
    _attr_icon = "mdi:weather-lightning-rainy"

    def __init__(self, runtime: ThresholdRuntime, title: str) -> None:
        self.runtime = runtime
        self._attr_unique_id = f"{runtime.subentry_id}_condition"
        self._attr_device_info = signal_device_info(
            runtime.subentry_id, title, "Bad weather", "bad-weather"
        )

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


class WeatherReasonSensor(SensorEntity):
    _attr_has_entity_name = True
    _attr_should_poll = False
    _attr_name = "Reason"
    _attr_icon = "mdi:message-text-outline"

    def __init__(self, runtime: ThresholdRuntime, title: str) -> None:
        self.runtime = runtime
        self._attr_unique_id = f"{runtime.subentry_id}_reason"
        self._attr_device_info = signal_device_info(
            runtime.subentry_id, title, "Bad weather", "bad-weather"
        )

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        self.async_on_remove(self.runtime.listen(self.async_write_ha_state))

    @property
    def native_value(self) -> str | None:
        return self.runtime.reason or None


class BadWeatherGuideSensor(SensorEntity):
    _attr_has_entity_name = True
    _attr_should_poll = False
    _attr_name = "Guide"
    _attr_icon = "mdi:information-outline"
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(self, runtime: ThresholdRuntime, title: str) -> None:
        self.runtime = runtime
        self._attr_unique_id = f"{runtime.subentry_id}_guide"
        self._attr_device_info = signal_device_info(
            runtime.subentry_id, title, "Bad weather", "bad-weather"
        )

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        self.async_on_remove(self.runtime.listen(self.async_write_ha_state))

    @property
    def native_value(self) -> str:
        return "Station rain or forecast storm → On"

    @property
    def extra_state_attributes(self) -> dict:
        conditions = self.runtime.data.get("storm_conditions") or [
            "lightning",
            "lightning-rainy",
            "pouring",
            "rainy",
        ]
        return {
            "summary": (
                "Bad weather turns on for live station rain or a matching forecast "
                "condition in the next 2 hours. Condition can stay sunny while On."
            ),
            "conditions": conditions,
            "reason": "Read the Reason sensor for the current sentence.",
            "docs": f"{DOCS_DEVICES}/bad-weather.md",
        }
