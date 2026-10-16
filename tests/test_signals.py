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
