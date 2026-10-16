"""Tests for weather signal math."""

from __future__ import annotations

import importlib.util
import sys
import types
from datetime import datetime, timedelta
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]


def load_logic():
    package_name = "custom_components.ha_utils"
    if package_name not in sys.modules:
        package = types.ModuleType(package_name)
        package.__path__ = [str(REPO / "custom_components" / "ha_utils")]  # type: ignore[attr-defined]
        sys.modules[package_name] = package
    name = f"{package_name}.logic"
    spec = importlib.util.spec_from_file_location(
        name, REPO / "custom_components" / "ha_utils" / "logic.py"
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


logic = load_logic()
START = datetime(2026, 10, 16, 12, 0, 0)


def engine(**overrides):
    options = logic.WindOptions(**overrides)
    item = logic.WindEngine(options)
    item.factor = options.factor_seed
    return item


def test_forecast_raises_risk_while_local_gust_is_zero() -> None:
    item = engine()
    item.set_forecast(START, 22.0, [22.0, 25.0])
    item.observe_gust(START, 0.0)
    snap = item.update(START, 0.0, True)

    assert snap.station_fresh is True
    assert snap.risk == round(max(0.0, 25.0 * 1.4), 1)
    assert snap.level == "big"
    assert snap.sample is None


def test_local_gust_is_not_lowered_by_a_calm_forecast() -> None:
    item = engine()
    item.set_forecast(START, 10.0, [10.0])
    item.observe_gust(START, 36.0)
    snap = item.update(START, 36.0, True)

    assert snap.risk == 36.0
    assert snap.level == "big"


def test_stale_forecast_is_left_out() -> None:
    item = engine()
    item.set_forecast(START - timedelta(hours=4), 40.0, [40.0])
    snap = item.update(START, None, False)

    assert snap.forecast_fresh is False
    assert snap.risk is None
    assert snap.level == "unknown"


def test_missing_numbers_do_not_unlock() -> None:
    item = engine()
    item.level = "all"
    snap = item.update(START, None, False)

    assert snap.level == "all"


def test_factor_sample_rejects_light_wind_and_blends_slowly() -> None:
    assert logic.factor_sample(10.5, 3.6, True) is None
    assert logic.factor_sample(0.0, 20.0, True) is None
    assert logic.factor_sample(20.0, 10.0, False) is None
    assert logic.factor_sample(20.0, 10.0, True) == 2.0
    assert logic.blend_factor(1.4, 2.0) == 1.5


def test_level_falls_only_on_the_calm_number() -> None:
    item = engine()
    item.level = "all"
    item.set_forecast(START, 10.0, [10.0])
    item.observe_gust(START, 30.0)
    snap = item.update(START, 30.0, True)

    assert snap.calm == 30.0
    assert snap.level == "big"

    item.level = "big"
    item.hourly = [10.0]
    item.sustained = 10.0
    item.samples = [(START, 10.0)]
    snap = item.update(START, 10.0, True)
    assert snap.level == "safe"


def test_temperature_prefers_a_fresh_station_and_keeps_forecast_warnings() -> None:
    merged = logic.merge_temperature(
        local=88.0,
        local_fresh=True,
        forecast_now=80.0,
        forecast_high=95.0,
        forecast_low=70.0,
        hot_line=90.0,
        cold_line=32.0,
    )
    assert merged.temperature == 88.0
    assert merged.hot is True
    assert merged.cold is False

    stale = logic.merge_temperature(
        local=100.0,
        local_fresh=False,
        forecast_now=70.0,
        forecast_high=70.0,
        forecast_low=20.0,
        hot_line=90.0,
        cold_line=32.0,
    )
    assert stale.temperature == 70.0
    assert stale.hot is False
    assert stale.cold is True


def test_bad_weather_turns_on_for_station_rain_or_forecast() -> None:
    condition, active = logic.merge_bad_weather(
        local_bad=True, forecast_condition="sunny", forecast_bad=False
    )
    assert condition == "rainy"
    assert active is True

    condition, active = logic.merge_bad_weather(
        local_bad=False, forecast_condition="lightning", forecast_bad=True
    )
    assert condition == "lightning"
    assert active is True

    condition, active = logic.merge_bad_weather(
        local_bad=True, forecast_condition="pouring", forecast_bad=True
    )
    assert condition == "pouring"
    assert active is True


def test_bad_weather_reason_names_the_forecast_hour() -> None:
    text = logic.describe_bad_weather(
        is_on=True,
        local_bad=False,
        station_configured=True,
        station_fresh=True,
        forecast_condition="sunny",
        forecast_hits=["rainy at 4:00 PM", "rainy at 5:00 PM"],
    )
    assert text == (
        "On because the forecast is rainy at 4:00 PM, rainy at 5:00 PM. "
        "The station is dry."
    )

    off = logic.describe_bad_weather(
        is_on=False,
        local_bad=False,
        station_configured=True,
        station_fresh=True,
        forecast_condition="sunny",
        forecast_hits=[],
    )
    assert off == "Off. The station is dry. The forecast is sunny."


def test_state_round_trip() -> None:
    item = engine()
    item.observe_gust(START, 12.0)
    item.set_forecast(START, 9.0, [11.0, 13.0])
    item.update(START, 12.0, True)
    raw = item.export_state()

    restored = engine()
    restored.import_state(raw)
    assert restored.factor == item.factor
    assert restored.level == item.level
    assert restored.samples == item.samples
    assert restored.hourly == [11.0, 13.0]
