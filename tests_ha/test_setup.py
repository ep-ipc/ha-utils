"""HA Utils signals running inside Home Assistant."""

from __future__ import annotations

import asyncio
from datetime import timedelta
import json
from pathlib import Path

import pytest
from pytest_homeassistant_custom_component.common import async_fire_time_changed

from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant, SupportsResponse
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers import issue_registry as ir
from homeassistant.util import dt as dt_util
from homeassistant.util.unit_system import US_CUSTOMARY_SYSTEM

from .conftest import DOMAIN, setup_entry, subentry

PACKAGE = Path(__file__).resolve().parents[1] / "custom_components" / "ha_utils"

WIND = {
    "gust_entity": "sensor.gust",
    "weather_entity": "weather.home",
    "factor_seed": 1.4,
    "rise_big": 30,
    "rise_all": 60,
    "fall_all": 45,
    "fall_big": 20,
}


def entity_id(hass: HomeAssistant, entry, kind: str, key: str) -> str:
    sub_id = next(s.subentry_id for s in entry.subentries.values() if s.subentry_type == kind)
    found = er.async_get(hass).async_get_entity_id(
        {"level": "sensor", "risk": "sensor", "calm": "sensor", "reason": "sensor",
         "temperature": "sensor", "condition": "sensor", "guide": "sensor",
         "hot": "binary_sensor", "cold": "binary_sensor", "active": "binary_sensor",
         "rise_big": "number", "rise_all": "number", "fall_big": "number", "fall_all": "number",
         "hot_threshold": "number", "cold_threshold": "number", "clear_margin": "number",
         "hold_minutes": "number"}[key],
        DOMAIN,
        f"{sub_id}_{key}",
    )
    assert found, key
    return found


def weather(hass: HomeAssistant, condition: str = "sunny", **attrs) -> None:
    hass.states.async_set(
        "weather.home",
        condition,
        {"temperature": 70, "temperature_unit": "°F", "wind_speed": 5, "wind_speed_unit": "mph", **attrs},
    )


def hours(*rows: dict) -> list[dict]:
    start = dt_util.now().replace(minute=0, second=0, microsecond=0)
    return [
        {"datetime": (start + timedelta(hours=index)).isoformat(), **row}
        for index, row in enumerate(rows)
    ]


def test_translations_match_strings() -> None:
    strings = json.loads((PACKAGE / "strings.json").read_text())
    english = json.loads((PACKAGE / "translations" / "en.json").read_text())
    assert strings == english


async def test_wind_converts_the_forecast_to_the_gust_unit(hass: HomeAssistant, forecast) -> None:
    hass.states.async_set("sensor.gust", "0", {"unit_of_measurement": "km/h", "device_class": "wind_speed"})
    weather(hass)
    forecast["weather.home"] = hours({"wind_speed": 25}, {"wind_speed": 25})
    entry = await setup_entry(hass, subentry("wind_signal", "Wind", {**WIND, "rise_big": 50, "rise_all": 95, "fall_all": 70, "fall_big": 30}))

    risk = hass.states.get(entity_id(hass, entry, "wind_signal", "risk"))
    # 25 mph is 40.2 km/h; times the 1.4 gust factor is 56.3 km/h.
    assert float(risk.state) == pytest.approx(56.3, abs=0.1)
    assert risk.attributes["unit_of_measurement"] == "km/h"
    level = hass.states.get(entity_id(hass, entry, "wind_signal", "level"))
    assert level.state == "advisory"
    assert "from the forecast" in level.attributes["reason"]
    reason = hass.states.get(entity_id(hass, entry, "wind_signal", "reason"))
    assert reason.state.startswith("Advisory because Risk is 56.3 km/h")


async def test_wind_expected_at(hass: HomeAssistant, forecast) -> None:
    hass.states.async_set("sensor.gust", "0", {"unit_of_measurement": "mph"})
    weather(hass)
    forecast["weather.home"] = hours({"wind_speed": 5}, {"wind_speed": 5}, {"wind_speed": 5}, {"wind_speed": 50})
    entry = await setup_entry(hass, subentry("wind_signal", "Wind", WIND))

    level = hass.states.get(entity_id(hass, entry, "wind_signal", "level"))
    assert level.state == "safe"
    assert level.attributes["advisory_expected_at"] is not None
    assert level.attributes["warning_expected_at"] == level.attributes["advisory_expected_at"]


async def test_bad_weather_reason_logs_without_crashing(hass: HomeAssistant, forecast) -> None:
    weather(hass, "sunny")
    forecast["weather.home"] = hours({"condition": "sunny"})
    entry = await setup_entry(
        hass, subentry("bad_weather", "Bad weather", {"weather_entity": "weather.home", "hold_minutes": 0})
    )
    active = entity_id(hass, entry, "bad_weather", "active")
    assert hass.states.get(active).state == "off"

    events = []
    hass.bus.async_listen("logbook_entry", events.append)
    weather(hass, "pouring")
    await hass.async_block_till_done()

    assert hass.states.get(active).state == "on"
    reason = hass.states.get(entity_id(hass, entry, "bad_weather", "reason")).state
    assert reason == "On because the forecast is pouring now."
    assert [event.data["message"] for event in events] == [reason]

    # It keeps updating after the Reason changes (the listener used to crash here).
    weather(hass, "sunny")
    await hass.async_block_till_done()
    assert hass.states.get(active).state == "off"


async def test_bad_weather_holds_after_the_storm(hass: HomeAssistant, forecast, freezer) -> None:
    weather(hass, "pouring")
    entry = await setup_entry(
        hass, subentry("bad_weather", "Bad weather", {"weather_entity": "weather.home", "hold_minutes": 30})
    )
    active = entity_id(hass, entry, "bad_weather", "active")
    assert hass.states.get(active).state == "on"

    weather(hass, "cloudy")
    await hass.async_block_till_done()
    state = hass.states.get(active)
    assert state.state == "on"
    assert state.attributes["held_until"] is not None

    freezer.tick(timedelta(minutes=31))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    assert hass.states.get(active).state == "off"


async def test_rain_total_only_counts_when_it_rises(hass: HomeAssistant, forecast) -> None:
    weather(hass, "cloudy")
    hass.states.async_set("sensor.rain_today", "0.4", {"device_class": "precipitation", "unit_of_measurement": "in"})
    entry = await setup_entry(
        hass,
        subentry(
            "bad_weather",
            "Bad weather",
            {"weather_entity": "weather.home", "station_entity": "sensor.rain_today", "hold_minutes": 0},
        ),
    )
    active = entity_id(hass, entry, "bad_weather", "active")
    assert hass.states.get(active).state == "off"

    hass.states.async_set("sensor.rain_today", "0.45", {"device_class": "precipitation", "unit_of_measurement": "in"})
    await hass.async_block_till_done()
    assert hass.states.get(active).state == "on"
    assert hass.states.get(entity_id(hass, entry, "bad_weather", "condition")).state == "rainy"


async def test_rain_rate_counts_while_above_zero(hass: HomeAssistant, forecast) -> None:
    weather(hass, "cloudy")
    hass.states.async_set("sensor.rain_rate", "0.2", {"device_class": "precipitation_intensity", "unit_of_measurement": "in/h"})
    entry = await setup_entry(
        hass,
        subentry(
            "bad_weather",
            "Bad weather",
            {"weather_entity": "weather.home", "station_entity": "sensor.rain_rate", "hold_minutes": 0},
        ),
    )
    assert hass.states.get(entity_id(hass, entry, "bad_weather", "active")).state == "on"


async def test_temperature_converts_the_station_and_clears_past_the_margin(
    hass: HomeAssistant, forecast
) -> None:
    hass.config.units = US_CUSTOMARY_SYSTEM
    weather(hass, temperature=70)
    hass.states.async_set("sensor.outside", "33", {"unit_of_measurement": "°C", "device_class": "temperature"})
    entry = await setup_entry(
        hass,
        subentry(
            "temperature",
            "Temperature",
            {
                "weather_entity": "weather.home",
                "station_entity": "sensor.outside",
                "hot_threshold": 90,
                "cold_threshold": 32,
                "clear_margin": 2,
            },
        ),
    )
    hot = entity_id(hass, entry, "temperature", "hot")
    temperature = hass.states.get(entity_id(hass, entry, "temperature", "temperature"))
    assert float(temperature.state) == pytest.approx(91.4)
    assert hass.states.get(hot).state == "on"

    hass.states.async_set("sensor.outside", "32", {"unit_of_measurement": "°C", "device_class": "temperature"})
    await hass.async_block_till_done()  # 89.6 °F: inside the margin
    assert hass.states.get(hot).state == "on"

    hass.states.async_set("sensor.outside", "31", {"unit_of_measurement": "°C", "device_class": "temperature"})
    await hass.async_block_till_done()  # 87.8 °F
    assert hass.states.get(hot).state == "off"
    reason = hass.states.get(entity_id(hass, entry, "temperature", "reason")).state
    assert reason.startswith("Neither.")


async def test_number_rejects_lines_out_of_order(hass: HomeAssistant, forecast) -> None:
    hass.states.async_set("sensor.gust", "0", {"unit_of_measurement": "mph"})
    weather(hass)
    entry = await setup_entry(hass, subentry("wind_signal", "Wind", WIND))

    with pytest.raises(ServiceValidationError):
        await hass.services.async_call(
            "number",
            "set_value",
            {"entity_id": entity_id(hass, entry, "wind_signal", "fall_big"), "value": 35},
            blocking=True,
        )
    await hass.services.async_call(
        "number",
        "set_value",
        {"entity_id": entity_id(hass, entry, "wind_signal", "fall_big"), "value": 15},
        blocking=True,
    )
    await hass.async_block_till_done()
    sub = next(iter(hass.config_entries.async_get_entry(entry.entry_id).subentries.values()))
    assert sub.data["fall_big"] == 15


async def test_stale_station_raises_a_repair(hass: HomeAssistant, forecast, freezer) -> None:
    weather(hass)
    hass.states.async_set("sensor.outside", "70", {"unit_of_measurement": "°F"})
    entry = await setup_entry(
        hass,
        subentry(
            "temperature",
            "Temperature",
            {"weather_entity": "weather.home", "station_entity": "sensor.outside", "hot_threshold": 90, "cold_threshold": 32},
        ),
    )
    sub_id = next(iter(entry.subentries))
    issues = ir.async_get(hass)
    assert issues.async_get_issue(DOMAIN, f"signal_source_stale_{sub_id}") is None

    freezer.tick(timedelta(hours=2, minutes=1))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    assert issues.async_get_issue(DOMAIN, f"signal_source_stale_{sub_id}") is not None

    hass.states.async_set("sensor.outside", "71", {"unit_of_measurement": "°F"})
    await hass.async_block_till_done()
    assert issues.async_get_issue(DOMAIN, f"signal_source_stale_{sub_id}") is None


async def test_device_triggers(hass: HomeAssistant, forecast) -> None:
    from custom_components.ha_utils.device_trigger import async_get_triggers

    hass.states.async_set("sensor.gust", "0", {"unit_of_measurement": "mph"})
    weather(hass)
    entry = await setup_entry(
        hass,
        subentry("wind_signal", "Wind", WIND),
        subentry("temperature", "Temperature", {"weather_entity": "weather.home", "hot_threshold": 90, "cold_threshold": 32}),
    )
    registry = dr.async_get(hass)
    types = {}
    for sub_id, sub in entry.subentries.items():
        device = registry.async_get_device(identifiers={(DOMAIN, sub_id)})
        types[sub.subentry_type] = {t["type"] for t in await async_get_triggers(hass, device.id)}
    assert types["wind_signal"] == {"level_safe", "level_advisory", "level_warning"}
    assert types["temperature"] == {"hot_on", "hot_off", "cold_on", "cold_off"}


async def test_device_trigger_fires(hass: HomeAssistant, forecast) -> None:
    from homeassistant.setup import async_setup_component

    from custom_components.ha_utils.device_trigger import async_get_triggers

    weather(hass, "sunny")
    entry = await setup_entry(
        hass, subentry("bad_weather", "Bad weather", {"weather_entity": "weather.home", "hold_minutes": 0})
    )
    sub_id = next(iter(entry.subentries))
    device = dr.async_get(hass).async_get_device(identifiers={(DOMAIN, sub_id)})
    trigger = next(t for t in await async_get_triggers(hass, device.id) if t["type"] == "bad_weather_on")
    calls = []
    hass.services.async_register("test", "record", lambda call: calls.append(call))
    assert await async_setup_component(
        hass,
        "automation",
        {"automation": {"trigger": trigger, "action": {"service": "test.record"}}},
    )
    weather(hass, "lightning")
    await hass.async_block_till_done()
    assert len(calls) == 1


async def test_diagnostics(hass: HomeAssistant, forecast) -> None:
    from custom_components.ha_utils.diagnostics import async_get_config_entry_diagnostics

    hass.states.async_set("sensor.gust", "12", {"unit_of_measurement": "mph"})
    weather(hass)
    entry = await setup_entry(hass, subentry("wind_signal", "Wind", WIND))
    result = await async_get_config_entry_diagnostics(hass, entry)
    (signal,) = result["signals"].values()
    assert signal["type"] == "wind_signal"
    assert signal["runtime"]["unit"] == "mph"
    assert signal["runtime"]["sources"]["gust_entity"]["state"] == "12"
    json.dumps(result)


async def test_unload_and_reload(hass: HomeAssistant, forecast) -> None:
    hass.states.async_set("sensor.gust", "0", {"unit_of_measurement": "mph"})
    weather(hass)
    entry = await setup_entry(
        hass,
        subentry("wind_signal", "Wind", WIND),
        subentry("bad_weather", "Bad weather", {"weather_entity": "weather.home"}),
    )
    assert await hass.config_entries.async_reload(entry.entry_id)
    await hass.async_block_till_done()
    assert entry.state is ConfigEntryState.LOADED
    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()
    assert hass.data[DOMAIN]["runtimes"] == {}
    assert hass.data[DOMAIN]["threshold_runtimes"] == {}


async def test_unload_during_startup_leaves_no_listeners(hass: HomeAssistant, forecast) -> None:
    from pytest_homeassistant_custom_component.common import MockConfigEntry

    hass.states.async_set("sensor.gust", "0", {"unit_of_measurement": "mph"})
    weather(hass)
    release = asyncio.Event()

    async def _slow_forecasts(call):
        await release.wait()
        return {"weather.home": {"forecast": []}}

    hass.services.async_register(
        "weather", "get_forecasts", _slow_forecasts, supports_response=SupportsResponse.ONLY
    )
    entry = MockConfigEntry(domain=DOMAIN, data={}, subentries_data=[subentry("wind_signal", "Wind", WIND)])
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    (runtime,) = hass.data[DOMAIN]["runtimes"].values()
    assert runtime._unsubs == []  # still waiting on the forecast
    assert await hass.config_entries.async_unload(entry.entry_id)
    release.set()
    await hass.async_block_till_done()
    assert runtime._stopped is True
    assert runtime._unsubs == []


async def test_minute_tick_does_not_rewrite_unchanged_state(hass: HomeAssistant, forecast, freezer) -> None:
    hass.states.async_set("sensor.gust", "40", {"unit_of_measurement": "mph"})
    weather(hass, "pouring")
    forecast["weather.home"] = hours({"wind_speed": 30, "condition": "pouring"}, {"wind_speed": 50, "condition": "rainy"})
    entry = await setup_entry(
        hass,
        subentry("wind_signal", "Wind", WIND),
        subentry("bad_weather", "Bad weather", {"weather_entity": "weather.home"}),
    )
    watched = [
        entity_id(hass, entry, "bad_weather", "active"),
        entity_id(hass, entry, "bad_weather", "reason"),
        entity_id(hass, entry, "wind_signal", "guide"),
    ]
    before = {item: hass.states.get(item).last_updated for item in watched}
    level_attrs = dict(hass.states.get(entity_id(hass, entry, "wind_signal", "level")).attributes)

    for _ in range(3):
        freezer.tick(timedelta(minutes=1))
        async_fire_time_changed(hass)
        await hass.async_block_till_done()

    assert {item: hass.states.get(item).last_updated for item in watched} == before
    after = hass.states.get(entity_id(hass, entry, "wind_signal", "level")).attributes
    assert after["advisory_expected_at"] == level_attrs["advisory_expected_at"]
    assert after["warning_expected_at"] == level_attrs["warning_expected_at"]
