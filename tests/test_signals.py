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
    assert snap.level == "advisory"
    assert snap.sample is None


def test_local_gust_is_not_lowered_by_a_calm_forecast() -> None:
    item = engine()
    item.set_forecast(START, 10.0, [10.0])
    item.observe_gust(START, 36.0)
    snap = item.update(START, 36.0, True)

    assert snap.risk == 36.0
    assert snap.level == "advisory"


def test_stale_forecast_is_left_out() -> None:
    item = engine()
    item.set_forecast(START - timedelta(hours=4), 40.0, [40.0])
    snap = item.update(START, None, False)

    assert snap.forecast_fresh is False
    assert snap.risk is None
    assert snap.level == "unknown"


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


def test_factor_sample_rejects_light_wind_and_blends_slowly() -> None:
    assert logic.factor_sample(10.5, 3.6, True) is None
    assert logic.factor_sample(0.0, 20.0, True) is None
    assert logic.factor_sample(20.0, 10.0, False) is None
    assert logic.factor_sample(20.0, 10.0, True) == 2.0
    assert logic.blend_factor(1.4, 2.0) == 1.5


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


def test_rain_total_counts_only_while_it_rises() -> None:
    tracker = logic.RainTracker()
    tracker.observe(START, 0.4)
    assert tracker.raining(START) is False  # a total already above 0 is not rain by itself

    tracker.observe(START + timedelta(minutes=5), 0.45)
    assert tracker.raining(START + timedelta(minutes=5)) is True
    assert tracker.raining(START + timedelta(minutes=34)) is True

    tracker.observe(START + timedelta(minutes=40), 0.45)
    assert tracker.raining(START + timedelta(minutes=40)) is False

    tracker.observe(START + timedelta(hours=12), 0.0)  # daily reset is not rain
    assert tracker.raining(START + timedelta(hours=12)) is False


def test_line_error_catches_flapping_wind_lines() -> None:
    good = {"rise_big": 30, "rise_all": 60, "fall_all": 45, "fall_big": 20}
    assert logic.line_error(good) is None
    assert logic.line_error({**good, "rise_all": 30}) == "rise_order"
    assert logic.line_error({**good, "fall_big": 45}) == "fall_order"
    assert logic.line_error({**good, "fall_big": 30, "fall_all": 50}) == "advisory_gap"
    assert logic.line_error({**good, "fall_all": 60}) == "warning_gap"


def test_line_error_requires_cold_below_hot() -> None:
    assert logic.line_error({"hot_threshold": 90, "cold_threshold": 32}) is None
    assert logic.line_error({"hot_threshold": 30, "cold_threshold": 30}) == "temperature_order"
    assert set(logic.LINE_ERRORS) >= {"rise_order", "fall_order", "advisory_gap", "warning_gap", "temperature_order"}


def test_hot_clears_only_past_the_margin() -> None:
    def merge(local: float, previous: bool) -> bool:
        return logic.merge_temperature(
            local=local,
            local_fresh=True,
            forecast_now=None,
            forecast_high=None,
            forecast_low=None,
            hot_line=90.0,
            cold_line=32.0,
            previous_hot=previous,
            margin=2.0,
        ).hot

    assert merge(90.5, False) is True
    assert merge(89.0, True) is True  # inside the margin, still hot
    assert merge(88.0, True) is False
    assert merge(89.0, False) is False  # margin never turns Hot on


def test_cold_clears_only_past_the_margin() -> None:
    merged = logic.merge_temperature(
        local=33.0,
        local_fresh=True,
        forecast_now=None,
        forecast_high=None,
        forecast_low=None,
        hot_line=90.0,
        cold_line=32.0,
        previous_cold=True,
        margin=2.0,
    )
    assert merged.cold is True


def test_apply_hold_keeps_bad_weather_on_for_the_hold() -> None:
    hold = timedelta(minutes=30)
    on, last, until = logic.apply_hold(True, None, START, hold)
    assert (on, last, until) == (True, START, None)

    later = START + timedelta(minutes=10)
    on, last, until = logic.apply_hold(False, last, later, hold)
    assert on is True and until == START + hold

    on, _last, until = logic.apply_hold(False, START, START + hold, hold)
    assert on is False and until is None

    assert logic.apply_hold(False, START, later, timedelta(0))[0] is False


def test_held_bad_weather_reason() -> None:
    text = logic.describe_bad_weather(
        is_on=True,
        local_bad=False,
        station_configured=True,
        station_fresh=True,
        forecast_condition="cloudy",
        forecast_hits=[],
        held_until="3:40 PM",
    )
    assert text == (
        "On, holding until 3:40 PM after the last bad weather. "
        "The station is dry. The forecast is cloudy."
    )


def test_wind_uses_forecast_stamps_and_reports_expected_hours() -> None:
    item = engine()
    stamps = [START - timedelta(hours=1), START, START + timedelta(hours=1), START + timedelta(hours=5)]
    item.set_forecast(START, 5.0, [100.0, 10.0, 12.0, 30.0], stamps)
    snap = item.update(START + timedelta(minutes=10), None, False)

    # The hour that already ended is left out of Risk.
    assert snap.risk == round(12.0 * 1.4, 1)
    assert snap.advisory_at == START + timedelta(hours=5)
    assert snap.warning_at is None


def test_forecast_stamps_round_trip() -> None:
    item = engine()
    item.set_forecast(START, 5.0, [10.0, 12.0], [START, START + timedelta(hours=1)])
    restored = engine()
    restored.import_state(item.export_state())
    assert restored.hourly_at == [START, START + timedelta(hours=1)]


def test_wind_reason_names_the_lane() -> None:
    item = engine()
    item.set_forecast(START, 10.0, [10.0])
    item.observe_gust(START, 36.0)
    snap = item.update(START, 36.0, True)
    assert logic.describe_wind(snap, item.options, "mph") == (
        "Advisory because Risk is 36 mph from the local gust, at or above 30 mph."
    )

    item = engine()
    item.set_forecast(START, 25.0, [25.0])
    snap = item.update(START, None, False)
    assert logic.describe_wind(snap, item.options, "mph") == (
        "Advisory because Risk is 35 mph from the forecast, at or above 30 mph."
    )

    item.level = "warning"
    item.set_forecast(START, 35.0, [35.0])
    snap = item.update(START, None, False)
    assert logic.describe_wind(snap, item.options, "mph") == (
        "Warning until Calm falls below 45 mph; Calm is 49 mph."
    )


def test_temperature_reason() -> None:
    merged = logic.TemperatureMerge(92.0, True, False)
    text = logic.describe_temperature(
        merged=merged,
        live=92.0,
        forecast_high=93.0,
        forecast_low=80.0,
        hot_line=90.0,
        cold_line=32.0,
        margin=2.0,
        unit="°F",
    )
    assert text == "Hot because the station reads 92 °F, above 90 °F."

    held = logic.describe_temperature(
        merged=logic.TemperatureMerge(89.0, True, False),
        live=89.0,
        forecast_high=89.0,
        forecast_low=80.0,
        hot_line=90.0,
        cold_line=32.0,
        margin=2.0,
        unit="°F",
    )
    assert held == "Hot until it is 88 °F or cooler."


def test_default_margin_follows_the_unit() -> None:
    assert logic.default_margin("°C") == 1.0
    assert logic.default_margin("°F") == 2.0
