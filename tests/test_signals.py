"""Tests for weather signal math and Guide text."""

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
DOCS = "https://github.com/ep-ipc/ha-utils/blob/main/docs/devices"


def engine(**overrides):
    options = logic.WindOptions(**overrides)
    item = logic.WindEngine(options)
    item.factor = options.factor_seed
    return item


def test_levels_are_safe_advisory_warning() -> None:
    assert logic.LEVELS == ("safe", "advisory", "warning")
    assert logic._LEGACY_LEVELS == {"big": "advisory", "all": "warning"}


def test_default_wind_options() -> None:
    options = logic.WindOptions()
    assert options.rise_big == 30.0
    assert options.rise_all == 60.0
    assert options.fall_all == 45.0
    assert options.fall_big == 20.0
    assert options.factor_seed == 1.4


def test_forecast_raises_risk_while_local_gust_is_zero() -> None:
    item = engine()
    item.set_forecast(START, 22.0, [22.0, 25.0])
    item.observe_gust(START, 0.0)
    snap = item.update(START, 0.0, True)

    assert snap.station_fresh is True
    assert snap.risk == round(max(0.0, 25.0 * 1.4), 1)
    assert snap.level == "advisory"
    assert snap.sample is None


def test_local_gust_is_not_lowered_by_a_calm_forecast() -> None:
    item = engine()
    item.set_forecast(START, 10.0, [10.0])
    item.observe_gust(START, 36.0)
    snap = item.update(START, 36.0, True)

    assert snap.risk == 36.0
    assert snap.level == "advisory"


def test_risk_uses_3m_local_or_2h_forecast_calm_uses_30m_or_1h() -> None:
    item = engine(factor_seed=1.0)
    item.factor = 1.0
    item.set_forecast(START, 12.0, [11.0, 14.0])
    item.observe_gust(START - timedelta(minutes=2), 8.0)
    item.observe_gust(START - timedelta(minutes=10), 9.0)
    item.observe_gust(START, 7.0)
    snap = item.update(START, 7.0, True)

    assert snap.gust_3m == 8.0
    assert snap.gust_30m == 9.0
    assert snap.forecast_1h == 12.0  # max(sustained 12, hourly[:1]=11)
    assert snap.forecast_2h == 14.0  # max(12, 11, 14)
    assert snap.risk == 14.0
    assert snap.calm == 12.0


def test_stale_forecast_is_left_out() -> None:
    item = engine()
    item.set_forecast(START - timedelta(hours=4), 40.0, [40.0])
    snap = item.update(START, None, False)

    assert snap.forecast_fresh is False
    assert snap.risk is None
    assert snap.level == "unknown"


def test_stale_station_drops_local_lane() -> None:
    item = engine(factor_seed=1.0)
    item.factor = 1.0
    item.set_forecast(START, 20.0, [20.0])
    item.observe_gust(START, 40.0)
    snap = item.update(START, 40.0, False)

    assert snap.station_fresh is False
    assert snap.risk == 20.0
    assert snap.calm == 20.0
    assert snap.gust_3m is None or snap.risk == 20.0


def test_missing_numbers_do_not_unlock() -> None:
    item = engine()
    item.level = "warning"
    snap = item.update(START, None, False)

    assert snap.level == "warning"


def test_legacy_level_names_still_latch() -> None:
    item = engine()
    item.level = "all"
    item.set_forecast(START, 10.0, [10.0])
    item.observe_gust(START, 30.0)
    snap = item.update(START, 30.0, True)
    assert snap.level == "advisory"


def test_import_state_maps_legacy_levels() -> None:
    item = engine()
    item.import_state({"level": "big", "factor": 1.4, "samples": []})
    assert item.level == "advisory"
    item.import_state({"level": "all", "factor": 1.4, "samples": []})
    assert item.level == "warning"
    item.import_state({"level": "nope", "factor": 1.4, "samples": []})
    assert item.level == "unknown"


def test_factor_sample_rejects_light_wind_and_blends_slowly() -> None:
    assert logic.factor_sample(10.5, 3.6, True) is None
    assert logic.factor_sample(0.0, 20.0, True) is None
    assert logic.factor_sample(20.0, 10.0, False) is None
    assert logic.factor_sample(20.0, 10.0, True) == 2.0
    assert logic.blend_factor(1.4, 2.0) == 1.5


def test_factor_steps_at_most_once_per_hour() -> None:
    item = engine(factor_seed=1.4)
    item.factor = 1.4
    item.set_forecast(START, 10.0, [10.0])
    item.observe_gust(START, 20.0)
    first = item.update(START, 20.0, True)
    assert first.sample == 2.0
    assert item.factor == 1.5

    item.observe_gust(START + timedelta(minutes=30), 30.0)
    second = item.update(START + timedelta(minutes=30), 30.0, True)
    assert second.sample == 3.0
    assert item.factor == 1.5  # no second blend yet

    item.observe_gust(START + timedelta(hours=1), 30.0)
    third = item.update(START + timedelta(hours=1), 30.0, True)
    assert third.sample == 3.0
    assert item.factor == 1.8


def test_level_falls_only_on_the_calm_number() -> None:
    item = engine()
    item.level = "warning"
    item.set_forecast(START, 10.0, [10.0])
    item.observe_gust(START, 30.0)
    snap = item.update(START, 30.0, True)

    assert snap.calm == 30.0
    assert snap.level == "advisory"

    item.level = "advisory"
    item.hourly = [10.0]
    item.sustained = 10.0
    item.samples = [(START, 10.0)]
    snap = item.update(START, 10.0, True)
    assert snap.level == "safe"


def test_latch_rises_on_risk_with_defaults() -> None:
    options = logic.WindOptions()
    assert logic.latch_level("safe", 29.9, 29.9, options) == "safe"
    assert logic.latch_level("safe", 30.0, 10.0, options) == "advisory"
    assert logic.latch_level("safe", 60.0, 10.0, options) == "warning"
    assert logic.latch_level("advisory", 60.0, 50.0, options) == "warning"


def test_latch_falls_on_calm_with_defaults() -> None:
    options = logic.WindOptions()
    assert logic.latch_level("warning", 70.0, 44.9, options) == "advisory"
    assert logic.latch_level("warning", 70.0, 19.9, options) == "safe"
    assert logic.latch_level("advisory", 25.0, 19.9, options) == "safe"
    assert logic.latch_level("warning", None, None, options) == "warning"


def test_latch_respects_custom_thresholds() -> None:
    options = logic.WindOptions(rise_big=25, rise_all=50, fall_all=40, fall_big=15)
    assert logic.latch_level("safe", 25.0, 10.0, options) == "advisory"
    assert logic.latch_level("advisory", 50.0, 45.0, options) == "warning"
    assert logic.latch_level("warning", 55.0, 39.0, options) == "advisory"
    assert logic.latch_level("advisory", 20.0, 14.0, options) == "safe"


def test_gust_window_discards_samples_older_than_30_minutes() -> None:
    item = engine()
    item.observe_gust(START - timedelta(minutes=31), 99.0)
    item.observe_gust(START, 5.0)
    assert all(stamp >= START - timedelta(minutes=30) for stamp, _ in item.samples)
    assert max(value for _, value in item.samples) == 5.0


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


def test_temperature_forecast_cannot_clear_live_hot_or_cold() -> None:
    hot = logic.merge_temperature(
        local=95.0,
        local_fresh=True,
        forecast_now=70.0,
        forecast_high=70.0,
        forecast_low=70.0,
        hot_line=90.0,
        cold_line=32.0,
    )
    assert hot.temperature == 95.0
    assert hot.hot is True

    cold = logic.merge_temperature(
        local=20.0,
        local_fresh=True,
        forecast_now=70.0,
        forecast_high=70.0,
        forecast_low=70.0,
        hot_line=90.0,
        cold_line=32.0,
    )
    assert cold.temperature == 20.0
    assert cold.cold is True


def test_temperature_uses_custom_lines() -> None:
    merged = logic.merge_temperature(
        local=81.0,
        local_fresh=True,
        forecast_now=70.0,
        forecast_high=70.0,
        forecast_low=70.0,
        hot_line=80.0,
        cold_line=40.0,
    )
    assert merged.hot is True
    assert merged.cold is False


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


def test_bad_weather_off_when_both_quiet() -> None:
    condition, active = logic.merge_bad_weather(
        local_bad=False, forecast_condition="sunny", forecast_bad=False
    )
    assert condition == "sunny"
    assert active is False


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


def test_bad_weather_reason_for_station_rain_and_stale_station() -> None:
    rain = logic.describe_bad_weather(
        is_on=True,
        local_bad=True,
        station_configured=True,
        station_fresh=True,
        forecast_condition="sunny",
        forecast_hits=[],
    )
    assert rain == "On because the station reports rain."

    stale = logic.describe_bad_weather(
        is_on=False,
        local_bad=False,
        station_configured=True,
        station_fresh=False,
        forecast_condition="sunny",
        forecast_hits=[],
    )
    assert "has not reported in the last 15 minutes" in stale

    none = logic.describe_bad_weather(
        is_on=False,
        local_bad=False,
        station_configured=False,
        station_fresh=False,
        forecast_condition=None,
        forecast_hits=[],
    )
    assert none == "Off."


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


def test_wind_guide_covers_rise_and_fall() -> None:
    state = logic.wind_guide_state(30, 60, 45, 20, "mph")
    assert state == (
        "↑ safe → advisory (30 mph) → warning (60 mph) · "
        "↓ warning → advisory (<45 mph) → safe (<20 mph)"
    )
    attrs = logic.wind_guide_attributes(30, 60, 45, 20, "mph", docs=f"{DOCS}/wind.md")
    assert "Risk raises the latch" in attrs["how_to_use"]
    assert "Weather forecast" in attrs["how_to_use"]
    assert attrs["rise_to_advisory"].startswith("When Risk reaches 30 mph")
    assert attrs["fall_to_safe"].startswith("When Calm falls below 20 mph")
    assert attrs["docs"].endswith("/wind.md")


def test_temperature_and_bad_weather_guides() -> None:
    assert logic.temperature_guide_state(90, 32) == "Cold below 32 · Hot above 90"
    temp_attrs = logic.temperature_guide_attributes(85, 40, docs=f"{DOCS}/temperature.md")
    assert temp_attrs["hot_above"] == "Hot turns on above 85."
    assert temp_attrs["cold_below"] == "Cold turns on below 40."

    assert logic.bad_weather_guide_state() == "Station rain or forecast storm → On"
    bad_attrs = logic.bad_weather_guide_attributes(
        ["lightning", "rainy"], docs=f"{DOCS}/bad-weather.md"
    )
    assert bad_attrs["conditions"] == ["lightning", "rainy"]
    assert "Reason sensor" in bad_attrs["reason"]
