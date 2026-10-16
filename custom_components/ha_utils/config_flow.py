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
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers import selector

from .const import DOMAIN, NAME

_STORM_DEFAULT = ["lightning", "lightning-rainy", "pouring", "rainy"]
_STORM_OPTIONS = [
    "lightning",
    "lightning-rainy",
    "pouring",
    "rainy",
    "hail",
    "windy",
    "windy-variant",
]


def _sensor_selector() -> selector.EntitySelector:
    return selector.EntitySelector(selector.EntitySelectorConfig(domain="sensor"))


def _weather_selector() -> selector.EntitySelector:
    return selector.EntitySelector(selector.EntitySelectorConfig(domain="weather"))


def _mph_selector(default: float) -> selector.NumberSelector:
    return selector.NumberSelector(
        selector.NumberSelectorConfig(
            min=0, max=150, step=1, mode=selector.NumberSelectorMode.BOX
        )
    )


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
            "hot_day": HotDaySubentryFlow,
            "cold_day": ColdDaySubentryFlow,
            "thunderstorm": ThunderstormSubentryFlow,
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
    """Shared name handling for signal subentries."""

    def _title_and_data(self, user_input: dict[str, Any]) -> tuple[str, dict[str, Any]]:
        data = dict(user_input)
        title = str(data.pop("name"))
        return title, data

    def _finish(self, user_input: dict[str, Any]):
        title, data = self._title_and_data(user_input)
        if self.source == SOURCE_RECONFIGURE:
            return self.async_update_and_abort(
                self._get_entry(),
                self._get_reconfigure_subentry(),
                title=title,
                data=data,
            )
        return self.async_create_entry(title=title, data=data)


class WindSignalSubentryFlow(_NamedSubentryFlow):
    """Collect the gust sensor, forecast, and shade-style thresholds."""

    async def async_step_reconfigure(self, user_input: dict[str, Any] | None = None):
        return await self.async_step_user(user_input)

    async def async_step_user(self, user_input: dict[str, Any] | None = None):
        if user_input is not None:
            if not user_input.get("heartbeat_entity"):
                user_input.pop("heartbeat_entity", None)
            return self._finish(user_input)

        defaults: dict[str, Any] = {}
        if self.source == SOURCE_RECONFIGURE:
            current = self._get_reconfigure_subentry()
            defaults = {"name": current.title, **dict(current.data)}

        fields: dict[Any, Any] = {
            vol.Required("name", default=defaults.get("name", "Wind")): str,
        }
        if defaults.get("gust_entity"):
            fields[vol.Required("gust_entity", default=defaults["gust_entity"])] = _sensor_selector()
        else:
            fields[vol.Required("gust_entity")] = _sensor_selector()
        if defaults.get("weather_entity"):
            fields[vol.Required("weather_entity", default=defaults["weather_entity"])] = _weather_selector()
        else:
            fields[vol.Required("weather_entity")] = _weather_selector()
        heartbeat_key: Any
        if defaults.get("heartbeat_entity"):
            heartbeat_key = vol.Optional(
                "heartbeat_entity",
                description={"suggested_value": defaults["heartbeat_entity"]},
            )
        else:
            heartbeat_key = vol.Optional("heartbeat_entity")
        fields[heartbeat_key] = _sensor_selector()
        fields.update(
            {
                vol.Required("factor_seed", default=defaults.get("factor_seed", 1.4)): selector.NumberSelector(
                    selector.NumberSelectorConfig(
                        min=1, max=3, step=0.05, mode=selector.NumberSelectorMode.BOX
                    )
                ),
                vol.Required("rise_big", default=defaults.get("rise_big", 30)): _mph_selector(30),
                vol.Required("rise_all", default=defaults.get("rise_all", 60)): _mph_selector(60),
                vol.Required("fall_all", default=defaults.get("fall_all", 45)): _mph_selector(45),
                vol.Required("fall_big", default=defaults.get("fall_big", 20)): _mph_selector(20),
            }
        )
        schema = vol.Schema(fields)
        return self.async_show_form(step_id="user", data_schema=schema)


class _TemperatureSubentryFlow(_NamedSubentryFlow):
    async def async_step_reconfigure(self, user_input: dict[str, Any] | None = None):
        return await self.async_step_user(user_input)

    async def async_step_user(self, user_input: dict[str, Any] | None = None):
        if user_input is not None:
            return self._finish(user_input)
        defaults: dict[str, Any] = {}
        if self.source == SOURCE_RECONFIGURE:
            current = self._get_reconfigure_subentry()
            defaults = {"name": current.title, **dict(current.data)}
        weather_key: Any = vol.Required("weather_entity")
        if defaults.get("weather_entity"):
            weather_key = vol.Required("weather_entity", default=defaults["weather_entity"])
        schema = vol.Schema(
            {
                vol.Required("name", default=defaults.get("name", self._default_name)): str,
                weather_key: _weather_selector(),
                vol.Required("threshold", default=defaults.get("threshold", self._default_threshold)): selector.NumberSelector(
                    selector.NumberSelectorConfig(
                        min=-50, max=150, step=1, mode=selector.NumberSelectorMode.BOX
                    )
                ),
            }
        )
        return self.async_show_form(step_id="user", data_schema=schema)


class HotDaySubentryFlow(_TemperatureSubentryFlow):
    _default_name = "Hot day"
    _default_threshold = 90


class ColdDaySubentryFlow(_TemperatureSubentryFlow):
    _default_name = "Cold day"
    _default_threshold = 32


class ThunderstormSubentryFlow(_NamedSubentryFlow):
    async def async_step_reconfigure(self, user_input: dict[str, Any] | None = None):
        return await self.async_step_user(user_input)

    async def async_step_user(self, user_input: dict[str, Any] | None = None):
        if user_input is not None:
            return self._finish(user_input)
        defaults: dict[str, Any] = {}
        if self.source == SOURCE_RECONFIGURE:
            current = self._get_reconfigure_subentry()
            defaults = {"name": current.title, **dict(current.data)}
        weather_key: Any = vol.Required("weather_entity")
        if defaults.get("weather_entity"):
            weather_key = vol.Required("weather_entity", default=defaults["weather_entity"])
        schema = vol.Schema(
            {
                vol.Required("name", default=defaults.get("name", "Thunderstorm")): str,
                weather_key: _weather_selector(),
                vol.Required(
                    "storm_conditions",
                    default=defaults.get("storm_conditions", _STORM_DEFAULT),
                ): selector.SelectSelector(
                    selector.SelectSelectorConfig(
                        options=_STORM_OPTIONS,
                        multiple=True,
                        custom_value=True,
                    )
                ),
            }
        )
        return self.async_show_form(step_id="user", data_schema=schema)
