"""Home Assistant wiring for weather signal entries."""

from __future__ import annotations

from datetime import datetime, timedelta
import logging
from typing import Any

from homeassistant.const import STATE_UNAVAILABLE, STATE_UNKNOWN
from homeassistant.core import Event, EventStateChangedData, HomeAssistant, State, callback
from homeassistant.helpers import issue_registry as ir
from homeassistant.helpers.event import (
    async_call_later,
    async_track_state_change_event,
    async_track_time_interval,
)
from homeassistant.helpers.storage import Store
from homeassistant.util import dt as dt_util

from .const import DOMAIN
from .logic import (
    WindEngine,
    WindOptions,
    describe_bad_weather,
    merge_bad_weather,
    merge_temperature,
)

_LOGGER = logging.getLogger(__name__)

FORECAST_EVERY = timedelta(minutes=15)
SAVE_DELAY = timedelta(seconds=10)


def _float_state(state: State | None) -> float | None:
    if state is None or state.state in (STATE_UNKNOWN, STATE_UNAVAILABLE, ""):
        return None
    try:
        return float(state.state)
    except (TypeError, ValueError):
        return None


def _reported_at(state: State | None) -> datetime | None:
    if state is None:
        return None
    reported = state.last_reported or state.last_updated
    if reported is None:
        return None
    return dt_util.as_local(reported)


class SignalRuntime:
    """Tracks sources for one signal subentry and notifies entities."""

    def __init__(self, hass: HomeAssistant, subentry_id: str, data: dict[str, Any]) -> None:
        self.hass = hass
        self.subentry_id = subentry_id
        self.data = data
        self._listeners: list[Any] = []
        self._unsubs: list[Any] = []
        self._save_unsub: Any = None
        self._store = Store(hass, 1, f"{DOMAIN}_signal_{subentry_id}")
        self.missing: list[str] = []

    def listen(self, update: Any) -> Any:
        self._listeners.append(update)

        def _unsub() -> None:
            if update in self._listeners:
                self._listeners.remove(update)

        return _unsub

    def _notify(self) -> None:
        for update in list(self._listeners):
            update()
        self._schedule_save()

    def _schedule_save(self) -> None:
        return None

    def async_start(self) -> Any:
        raise NotImplementedError

    def _stop(self) -> None:
        for unsub in self._unsubs:
            unsub()
        self._unsubs.clear()
        if self._save_unsub is not None:
            self._save_unsub()
            self._save_unsub = None

    def _set_issue(self) -> None:
        issue_id = f"signal_source_missing_{self.subentry_id}"
        if not self.missing:
            ir.async_delete_issue(self.hass, DOMAIN, issue_id)
            return
        ir.async_create_issue(
            self.hass,
            DOMAIN,
            issue_id,
            is_fixable=False,
            severity=ir.IssueSeverity.WARNING,
            translation_key="signal_source_missing",
            translation_placeholders={"entities": ", ".join(self.missing)},
        )


class WindSignalRuntime(SignalRuntime):
    """Gust plus forecast, publishing risk, calm, level, and gust factor."""

    def __init__(self, hass: HomeAssistant, subentry_id: str, data: dict[str, Any]) -> None:
        super().__init__(hass, subentry_id, data)
        seed = float(data.get("factor_seed", 1.4))
        self.engine = WindEngine(
            WindOptions(
                rise_big=float(data.get("rise_big", 30)),
                rise_all=float(data.get("rise_all", 60)),
                fall_big=float(data.get("fall_big", 20)),
                fall_all=float(data.get("fall_all", 45)),
                factor_seed=seed,
            )
        )
        self.engine.factor = seed
        gust_state = hass.states.get(str(data.get("gust_entity", "")))
        unit = None if gust_state is None else gust_state.attributes.get("unit_of_measurement")
        self.unit = unit or "mph"

    def async_start(self) -> Any:
        self.hass.async_create_task(self._async_start())
        return self._stop

    async def _async_start(self) -> None:
        stored = await self._store.async_load()
        if isinstance(stored, dict):
            self.engine.import_state(stored)
        self._refresh(dt_util.now())
        await self._async_poll_forecast()
        gust = self.data["gust_entity"]
        heartbeat = self.data.get("heartbeat_entity") or gust
        watched = {gust, heartbeat, self.data["weather_entity"]}

        @callback
        def _state_changed(_event: Event[EventStateChangedData]) -> None:
            self._refresh(dt_util.now())

        self._unsubs.append(async_track_state_change_event(self.hass, list(watched), _state_changed))
        self._unsubs.append(
            async_track_time_interval(self.hass, self._async_poll_forecast, FORECAST_EVERY)
        )

    def _schedule_save(self) -> None:
        if self._save_unsub is not None:
            return

        @callback
        def _save(_now: datetime) -> None:
            self._save_unsub = None
            self.hass.async_create_task(self._store.async_save(self.engine.export_state()))

        self._save_unsub = async_call_later(self.hass, SAVE_DELAY.total_seconds(), _save)

    def _refresh(self, now: datetime) -> None:
        gust_entity = self.data["gust_entity"]
        heartbeat_entity = self.data.get("heartbeat_entity") or gust_entity
        missing = [
            entity
            for entity in (gust_entity, self.data["weather_entity"])
            if self.hass.states.get(entity) is None
        ]
        self.missing = missing
        self._set_issue()
        gust_state = self.hass.states.get(gust_entity)
        gust = _float_state(gust_state)
        if gust is not None:
            self.engine.observe_gust(now, gust)
        heartbeat = self.hass.states.get(heartbeat_entity)
        reported = _reported_at(heartbeat)
        station_fresh = (
            heartbeat is not None
            and heartbeat.state not in (STATE_UNKNOWN, STATE_UNAVAILABLE)
            and reported is not None
            and (now - reported).total_seconds() < 15 * 60
        )
        self.engine.update(now, gust, station_fresh and not missing)
        self._notify()

    async def _async_poll_forecast(self, _now: datetime | None = None) -> None:
        weather = self.data["weather_entity"]
        now = dt_util.now()
        if self.hass.states.get(weather) is None:
            self._refresh(now)
            return
        try:
            response = await self.hass.services.async_call(
                "weather",
                "get_forecasts",
                {"type": "hourly"},
                target={"entity_id": weather},
                blocking=True,
                return_response=True,
            )
        except Exception:  # noqa: BLE001 - keep the last good forecast
            _LOGGER.warning("Wind signal could not read the forecast for %s", weather)
            self._refresh(now)
            return
        payload = (response or {}).get(weather, {})
        hourly = []
        for row in payload.get("forecast", []):
            speed = row.get("wind_speed")
            if isinstance(speed, (int, float)):
                hourly.append(float(speed))
        sustained = _float_state(self.hass.states.get(weather))
        if sustained is None:
            raw = self.hass.states.get(weather)
            attr = None if raw is None else raw.attributes.get("wind_speed")
            if isinstance(attr, (int, float)):
                sustained = float(attr)
        self.engine.set_forecast(now, sustained, hourly)
        self._refresh(now)


def async_get_threshold_runtime(
    hass: HomeAssistant,
    entry: Any,
    subentry_id: str,
    data: dict[str, Any],
    kind: str,
) -> ThresholdRuntime:
    """Return the shared runtime for a temperature or bad-weather entry."""

    runtimes: dict[str, ThresholdRuntime] = hass.data.setdefault(DOMAIN, {}).setdefault(
        "threshold_runtimes", {}
    )
    runtime = runtimes.get(subentry_id)
    if runtime is None:
        runtime = ThresholdRuntime(hass, subentry_id, data, kind)
        runtimes[subentry_id] = runtime
        entry.async_on_unload(runtime.async_start())

        def _drop() -> None:
            runtimes.pop(subentry_id, None)

        entry.async_on_unload(_drop)
    return runtime


_STORM_DEFAULT = ["lightning", "lightning-rainy", "pouring", "rainy"]
_STATION_FRESH = timedelta(minutes=15)
_FORECAST_WINDOW = timedelta(hours=2)


class ThresholdRuntime(SignalRuntime):
    """Temperature or bad weather from a station, a forecast, or both."""

    def __init__(self, hass: HomeAssistant, subentry_id: str, data: dict[str, Any], kind: str) -> None:
        super().__init__(hass, subentry_id, data)
        self.kind = kind
        self.temperature: float | None = None
        self.local_temperature: float | None = None
        self.forecast_temperature: float | None = None
        self.condition: str | None = None
        self.station_fresh = False
        self.local_bad = False
        self.forecast_bad = False
        self.hot = False
        self.cold = False
        self.is_on = False
        self.reason = ""
        self._forecast_high: float | None = None
        self._forecast_low: float | None = None
        self._forecast_conditions: list[str] = []
        self._forecast_hits: list[str] = []

    def async_start(self) -> Any:
        self.hass.async_create_task(self._async_start())
        return self._stop

    async def _async_start(self) -> None:
        await self._async_poll_forecast()
        watched = [self.data["weather_entity"]]
        station = self.data.get("station_entity")
        if isinstance(station, str) and station:
            watched.append(station)

        @callback
        def _state_changed(_event: Event[EventStateChangedData]) -> None:
            self._refresh(dt_util.now())

        self._unsubs.append(async_track_state_change_event(self.hass, watched, _state_changed))
        self._unsubs.append(
            async_track_time_interval(self.hass, self._async_poll_forecast, FORECAST_EVERY)
        )

    def _line(self, key: str, fallback: float) -> float:
        value = self.data.get(key, fallback)
        return float(value) if isinstance(value, (int, float)) else fallback

    def _conditions(self) -> list[str]:
        raw = self.data.get("storm_conditions") or _STORM_DEFAULT
        return [str(item) for item in raw]

    def _refresh(self, now: datetime) -> None:
        weather = self.data["weather_entity"]
        station_id = self.data.get("station_entity")
        missing = [weather] if self.hass.states.get(weather) is None else []
        if isinstance(station_id, str) and station_id and self.hass.states.get(station_id) is None:
            missing.append(station_id)
        self.missing = missing
        self._set_issue()

        station = self.hass.states.get(station_id) if isinstance(station_id, str) else None
        reported = _reported_at(station)
        self.station_fresh = (
            station is not None
            and station.state not in (STATE_UNKNOWN, STATE_UNAVAILABLE)
            and reported is not None
            and (now - reported).total_seconds() < _STATION_FRESH.total_seconds()
        )
        self.local_temperature = _float_state(station) if self.kind == "temperature" else None
        self.local_bad = self.station_fresh and _station_reports_bad_weather(station)
        forecast_state = self.hass.states.get(weather)
        forecast_condition = None if forecast_state is None else forecast_state.state
        conditions = self._conditions()
        self.forecast_bad = forecast_condition in conditions or any(
            item in conditions for item in self._forecast_conditions
        )
        if self.kind == "temperature":
            merged = merge_temperature(
                local=self.local_temperature,
                local_fresh=self.station_fresh,
                forecast_now=self.forecast_temperature,
                forecast_high=self._forecast_high,
                forecast_low=self._forecast_low,
                hot_line=self._line("hot_threshold", 90),
                cold_line=self._line("cold_threshold", 32),
            )
            self.temperature = merged.temperature
            self.hot = merged.hot
            self.cold = merged.cold
            self.condition = forecast_condition
            self.is_on = self.hot or self.cold
        else:
            self.condition, self.is_on = merge_bad_weather(
                local_bad=self.local_bad,
                forecast_condition=forecast_condition,
                forecast_bad=self.forecast_bad,
            )
            self.temperature = None
            self.hot = False
            self.cold = False
            self.reason = describe_bad_weather(
                is_on=self.is_on,
                local_bad=self.local_bad,
                station_configured=isinstance(station_id, str) and bool(station_id),
                station_fresh=self.station_fresh,
                forecast_condition=forecast_condition,
                forecast_hits=self._forecast_hits,
            )
        self._notify()

    async def _async_poll_forecast(self, _now: datetime | None = None) -> None:
        weather = self.data["weather_entity"]
        now = dt_util.now()
        state = self.hass.states.get(weather)
        if state is None:
            self.forecast_temperature = None
            self._forecast_high = None
            self._forecast_low = None
            self._forecast_conditions = []
            self._forecast_hits = []
            self._refresh(now)
            return
        raw_temp = state.attributes.get("temperature")
        current = float(raw_temp) if isinstance(raw_temp, (int, float)) else None
        hourly_temps: list[float] = []
        hourly_conditions: list[str] = []
        hits: list[str] = []
        conditions = self._conditions()
        if state.state in conditions:
            hits.append(f"{state.state} now")
        try:
            response = await self.hass.services.async_call(
                "weather",
                "get_forecasts",
                {"type": "hourly"},
                target={"entity_id": weather},
                blocking=True,
                return_response=True,
            )
        except Exception:  # noqa: BLE001 - current weather attributes still apply
            _LOGGER.warning("Signal could not read the forecast for %s", weather)
            response = None
        payload = (response or {}).get(weather, {})
        for row in payload.get("forecast", []):
            stamp = dt_util.parse_datetime(str(row.get("datetime") or ""))
            if stamp is not None and dt_util.as_local(stamp) - now > _FORECAST_WINDOW:
                continue
            if stamp is None and len(hourly_temps) >= 2 and len(hourly_conditions) >= 2:
                continue
            temp = row.get("temperature")
            if isinstance(temp, (int, float)):
                hourly_temps.append(float(temp))
            condition = row.get("condition")
            if isinstance(condition, str):
                hourly_conditions.append(condition)
                if condition in conditions and stamp is not None:
                    label = dt_util.as_local(stamp).strftime("%I:%M %p").lstrip("0")
                    hits.append(f"{condition} at {label}")
        temps = [current] if current is not None else []
        temps.extend(hourly_temps)
        self.forecast_temperature = current
        self._forecast_high = max(temps) if temps else None
        self._forecast_low = min(temps) if temps else None
        self._forecast_conditions = hourly_conditions
        self._forecast_hits = hits
        self._refresh(now)


def _station_reports_bad_weather(state: State | None) -> bool:
    if state is None or state.state in (STATE_UNKNOWN, STATE_UNAVAILABLE, ""):
        return False
    if state.entity_id.startswith("binary_sensor.") or state.attributes.get("device_class") == "moisture":
        return state.state == "on"
    amount = _float_state(state)
    return amount is not None and amount > 0
