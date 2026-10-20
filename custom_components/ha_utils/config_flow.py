"""Config flow for Home Assistant Utils."""

from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant.config_entries import (
    SOURCE_RECONFIGURE,
    ConfigEntry,
    ConfigFlow,
    ConfigSubentryFlow,
)
from homeassistant.const import UnitOfSpeed, UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResult
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import selector
from homeassistant.util.unit_conversion import SpeedConverter, TemperatureConverter

from .const import DOMAIN, NAME, STORM_DEFAULT, STORM_OPTIONS
from .logic import (
    HOLD_MINUTES,
    TEMPERATURE_LINES_F,
    WIND_LINES_MPH,
    default_margin,
    line_error,
)


def _speed_unit(hass: HomeAssistant) -> str:
    """Wind sensors and weather entities show km/h on metric installs, mph otherwise."""

    if hass.config.units.temperature_unit == UnitOfTemperature.CELSIUS:
        return UnitOfSpeed.KILOMETERS_PER_HOUR
    return UnitOfSpeed.MILES_PER_HOUR


def _wind_lines(unit: str) -> dict[str, float]:
    try:
        return {
            key: float(round(SpeedConverter.convert(value, UnitOfSpeed.MILES_PER_HOUR, unit)))
            for key, value in WIND_LINES_MPH.items()
        }
    except HomeAssistantError:
        return dict(WIND_LINES_MPH)


def _default_lines(hass: HomeAssistant) -> dict[str, float]:
    """Starting lines in the house unit system."""

    temperature_unit = hass.config.units.temperature_unit
    lines = _wind_lines(_speed_unit(hass))
    for key, value in TEMPERATURE_LINES_F.items():
        lines[key] = float(
            round(TemperatureConverter.convert(value, UnitOfTemperature.FAHRENHEIT, temperature_unit))
        )
    lines["clear_margin"] = default_margin(temperature_unit)
    lines["hold_minutes"] = HOLD_MINUTES
    return lines


def _entity_selector(
    domain: str | list[str], device_class: str | list[str] | None = None
) -> selector.EntitySelector:
    config: dict[str, Any] = {"domain": domain}
    if device_class is not None:
        config["device_class"] = device_class
    return selector.EntitySelector(selector.EntitySelectorConfig(**config))


def _number_selector(minimum: float, maximum: float, step: float = 1) -> selector.NumberSelector:
    return selector.NumberSelector(
        selector.NumberSelectorConfig(
            min=minimum, max=maximum, step=step, mode=selector.NumberSelectorMode.BOX
        )
    )


def _entity_field(fields: dict[Any, Any], key: str, defaults: dict[str, Any], required: bool, value: Any) -> None:
    """Required fields carry their default; optional ones only suggest it so they can be cleared."""

    current = defaults.get(key)
    if required:
        marker: Any = vol.Required(key, default=current) if current else vol.Required(key)
    elif current:
        marker = vol.Optional(key, description={"suggested_value": current})
    else:
        marker = vol.Optional(key)
    fields[marker] = value


class HaUtilsConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Home Assistant Utils."""

    VERSION = 1

    @classmethod
    def async_get_supported_subentry_types(
        cls, config_entry: ConfigEntry
    ) -> dict[str, type[ConfigSubentryFlow]]:
        """Signal entries a user can add under this integration."""

        return {
            "wind_signal": WindSignalSubentryFlow,
            "temperature": TemperatureSubentryFlow,
            "bad_weather": BadWeatherSubentryFlow,
        }

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Create the single integration entry."""

        if self._async_current_entries():
            return self.async_abort(reason="single_instance_allowed")

        if user_input is not None:
            return self.async_create_entry(title=NAME, data={})

        return self.async_show_form(step_id="user", data_schema=vol.Schema({}))


class _NamedSubentryFlow(ConfigSubentryFlow):
    """Shared name, defaults, and line checks for signal subentries."""

    default_name = ""
    optional_entity = ""

    async def async_step_reconfigure(self, user_input: dict[str, Any] | None = None):
        return await self.async_step_user(user_input)

    async def async_step_user(self, user_input: dict[str, Any] | None = None):
        errors: dict[str, str] = {}
        if user_input is not None:
            user_input = dict(user_input)
            if self.optional_entity and not user_input.get(self.optional_entity):
                user_input.pop(self.optional_entity, None)
            self._before_save(user_input)
            error = line_error(user_input)
            if error is None:
                return self._finish(user_input)
            errors["base"] = error
        defaults = self._defaults(user_input)
        return self.async_show_form(
            step_id="user", data_schema=vol.Schema(self._fields(defaults)), errors=errors
        )

    def _before_save(self, user_input: dict[str, Any]) -> None:
        return None

    def _fields(self, defaults: dict[str, Any]) -> dict[Any, Any]:
        raise NotImplementedError

    def _defaults(self, user_input: dict[str, Any] | None) -> dict[str, Any]:
        defaults: dict[str, Any] = {"name": self.default_name, **_default_lines(self.hass)}
        if self.source == SOURCE_RECONFIGURE:
            current = self._get_reconfigure_subentry()
            defaults.update({"name": current.title, **dict(current.data)})
        if user_input:
            defaults.update(user_input)
        return defaults

    def _finish(self, user_input: dict[str, Any]):
        data = dict(user_input)
        title = str(data.pop("name"))
        if self.source == SOURCE_RECONFIGURE:
            return self.async_update_and_abort(
                self._get_entry(),
                self._get_reconfigure_subentry(),
                title=title,
                data=data,
            )
        return self.async_create_entry(title=title, data=data)


class WindSignalSubentryFlow(_NamedSubentryFlow):
    """Collect the gust sensor, forecast, and rise and fall lines."""

    default_name = "Wind"
    optional_entity = "heartbeat_entity"

    def _before_save(self, user_input: dict[str, Any]) -> None:
        # Untouched starting lines follow the gust sensor's own unit.
        if self.source == SOURCE_RECONFIGURE:
            return
        shown = _wind_lines(_speed_unit(self.hass))
        if any(user_input.get(key) != value for key, value in shown.items()):
            return
        gust = self.hass.states.get(str(user_input.get("gust_entity", "")))
        unit = None if gust is None else gust.attributes.get("unit_of_measurement")
        if unit and unit != _speed_unit(self.hass):
            user_input.update(_wind_lines(str(unit)))

    def _fields(self, defaults: dict[str, Any]) -> dict[Any, Any]:
        fields: dict[Any, Any] = {vol.Required("name", default=defaults["name"]): str}
        _entity_field(fields, "gust_entity", defaults, True, _entity_selector("sensor", "wind_speed"))
        _entity_field(fields, "weather_entity", defaults, True, _entity_selector("weather"))
        _entity_field(fields, "heartbeat_entity", defaults, False, _entity_selector("sensor"))
        fields[vol.Required("factor_seed", default=defaults.get("factor_seed", 1.4))] = _number_selector(1, 3, 0.05)
        for key in ("rise_big", "rise_all", "fall_all", "fall_big"):
            fields[vol.Required(key, default=defaults[key])] = _number_selector(0, 150)
        return fields


class TemperatureSubentryFlow(_NamedSubentryFlow):
    default_name = "Temperature"
    optional_entity = "station_entity"

    def _fields(self, defaults: dict[str, Any]) -> dict[Any, Any]:
        fields: dict[Any, Any] = {vol.Required("name", default=defaults["name"]): str}
        _entity_field(fields, "station_entity", defaults, False, _entity_selector("sensor", "temperature"))
        _entity_field(fields, "weather_entity", defaults, True, _entity_selector("weather"))
        fields[vol.Required("hot_threshold", default=defaults["hot_threshold"])] = _number_selector(-50, 150)
        fields[vol.Required("cold_threshold", default=defaults["cold_threshold"])] = _number_selector(-50, 150)
        fields[vol.Required("clear_margin", default=defaults["clear_margin"])] = _number_selector(0, 20, 0.5)
        return fields


class BadWeatherSubentryFlow(_NamedSubentryFlow):
    default_name = "Bad weather"
    optional_entity = "station_entity"

    def _fields(self, defaults: dict[str, Any]) -> dict[Any, Any]:
        fields: dict[Any, Any] = {vol.Required("name", default=defaults["name"]): str}
        _entity_field(
            fields,
            "station_entity",
            defaults,
            False,
            _entity_selector(
                ["binary_sensor", "sensor"], ["moisture", "precipitation", "precipitation_intensity"]
            ),
        )
        _entity_field(fields, "weather_entity", defaults, True, _entity_selector("weather"))
        fields[
            vol.Required("storm_conditions", default=defaults.get("storm_conditions", STORM_DEFAULT))
        ] = selector.SelectSelector(
            selector.SelectSelectorConfig(options=STORM_OPTIONS, multiple=True, custom_value=True)
        )
        fields[vol.Required("hold_minutes", default=defaults["hold_minutes"])] = _number_selector(0, 240)
        return fields
