"""Signal subentry flows."""

from __future__ import annotations

from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.util.unit_system import METRIC_SYSTEM, US_CUSTOMARY_SYSTEM

from .conftest import setup_entry


async def _start(hass: HomeAssistant, kind: str):
    entry = await setup_entry(hass)
    result = await hass.config_entries.subentries.async_init((entry.entry_id, kind), context={"source": "user"})
    return entry, result


def _default(result, key: str):
    for marker in result["data_schema"].schema:
        if str(marker) == key:
            return marker.default()
    raise KeyError(key)


async def test_wind_rejects_lines_out_of_order(hass: HomeAssistant) -> None:
    hass.states.async_set("sensor.gust", "0", {"unit_of_measurement": "mph", "device_class": "wind_speed"})
    hass.states.async_set("weather.home", "sunny", {})
    entry, result = await _start(hass, "wind_signal")
    assert result["type"] is FlowResultType.FORM

    user_input = {
        "name": "Wind",
        "gust_entity": "sensor.gust",
        "weather_entity": "weather.home",
        "factor_seed": 1.4,
        "rise_big": 30,
        "rise_all": 60,
        "fall_all": 45,
        "fall_big": 35,
    }
    result = await hass.config_entries.subentries.async_configure(result["flow_id"], user_input)
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "advisory_gap"}

    result = await hass.config_entries.subentries.async_configure(result["flow_id"], {**user_input, "fall_big": 20})
    assert result["type"] is FlowResultType.CREATE_ENTRY
    (sub,) = hass.config_entries.async_get_entry(entry.entry_id).subentries.values()
    assert sub.data["fall_big"] == 20


async def test_metric_defaults(hass: HomeAssistant) -> None:
    hass.config.units = METRIC_SYSTEM
    _entry, result = await _start(hass, "temperature")
    assert _default(result, "hot_threshold") == 32
    assert _default(result, "cold_threshold") == 0
    assert _default(result, "clear_margin") == 1.0

    result = await hass.config_entries.subentries.async_init(
        (_entry.entry_id, "wind_signal"), context={"source": "user"}
    )
    assert [_default(result, key) for key in ("rise_big", "rise_all", "fall_all", "fall_big")] == [48, 97, 72, 32]


async def test_untouched_wind_defaults_follow_the_gust_unit(hass: HomeAssistant) -> None:
    hass.config.units = US_CUSTOMARY_SYSTEM
    hass.states.async_set("sensor.gust", "0", {"unit_of_measurement": "m/s", "device_class": "wind_speed"})
    hass.states.async_set("weather.home", "sunny", {})
    entry, result = await _start(hass, "wind_signal")
    user_input = {
        "name": "Wind",
        "gust_entity": "sensor.gust",
        "weather_entity": "weather.home",
        "factor_seed": 1.4,
        "rise_big": 30,
        "rise_all": 60,
        "fall_all": 45,
        "fall_big": 20,
    }
    result = await hass.config_entries.subentries.async_configure(result["flow_id"], user_input)
    assert result["type"] is FlowResultType.CREATE_ENTRY
    (sub,) = hass.config_entries.async_get_entry(entry.entry_id).subentries.values()
    assert [sub.data[key] for key in ("rise_big", "rise_all", "fall_all", "fall_big")] == [13, 27, 20, 9]
