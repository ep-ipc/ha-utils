"""Home Assistant wiring for weather signal entries."""

from __future__ import annotations

from datetime import datetime, timedelta
import logging
from typing import Any

from homeassistant.const import STATE_UNAVAILABLE, STATE_UNKNOWN
from homeassistant.core import Event, EventStateChangedData, HomeAssistant, State, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import issue_registry as ir
from homeassistant.helpers.event import (
    async_call_later,
    async_track_state_change_event,
    async_track_time_interval,
)
from homeassistant.helpers.storage import Store
from homeassistant.util import dt as dt_util
from homeassistant.util.unit_conversion import SpeedConverter, TemperatureConverter

from .const import DOMAIN, STORM_DEFAULT
from .logic import (
    HOLD_MINUTES,
    HOUR,
    RainTracker,
    WindEngine,
    WindOptions,
    apply_hold,
    default_margin,
    describe_bad_weather,
    describe_temperature,
    describe_wind,
    merge_bad_weather,
    merge_temperature,
)

_LOGGER = logging.getLogger(__name__)

FORECAST_EVERY = timedelta(minutes=15)
FORECAST_REUSE = timedelta(minutes=5)
FORECAST_AHEAD = timedelta(hours=24)
TICK_EVERY = timedelta(minutes=1)
SAVE_DELAY = timedelta(seconds=10)
STATION_FRESH = timedelta(minutes=15)
STATION_STALE = timedelta(hours=2)
_FORECAST_WINDOW = timedelta(hours=2)
_FORECAST_CACHE = "forecast_cache"
WIND_RUNTIMES = "runtimes"
THRESHOLD_RUNTIMES = "threshold_runtimes"


def _float_state(state: State | None) -> float | None:
    if state is None or state.state in (STATE_UNKNOWN, STATE_UNAVAILABLE, ""):
        return None
    try:
        return float(state.state)
    except (TypeError, ValueError):
        return None


def _convert(converter: Any, value: float, from_unit: object, to_unit: object) -> float:
    """Convert between units, keeping the value when either unit is unknown."""

    if not from_unit or not to_unit or from_unit == to_unit:
        return value
    try:
        return float(converter.convert(value, str(from_unit), str(to_unit)))
    except (HomeAssistantError, ValueError):
        return value


def _reported_at(state: State | None) -> datetime | None:
    if state is None:
        return None
    reported = state.last_reported or state.last_updated
    if reported is None:
        return None
    return dt_util.as_local(reported)


def _is_fresh(state: State | None, now: datetime) -> bool:
    reported = _reported_at(state)
    return (
        state is not None
        and state.state not in (STATE_UNKNOWN, STATE_UNAVAILABLE)
        and reported is not None
        and now - reported < STATION_FRESH
    )


def _is_stale(state: State | None, now: datetime) -> bool:
    """A source that exists but has not reported for hours."""

    reported = _reported_at(state)
    return state is not None and reported is not None and now - reported >= STATION_STALE


def _clock(when: datetime) -> str:
    return dt_util.as_local(when).strftime("%I:%M %p").lstrip("0")


def _stamp(row: dict) -> datetime | None:
    stamp = dt_util.parse_datetime(str(row.get("datetime") or ""))
    return None if stamp is None else dt_util.as_local(stamp)


async def _async_fetch_hourly(hass: HomeAssistant, weather: str) -> list[dict] | None:
    try:
        response = await hass.services.async_call(
            "weather",
            "get_forecasts",
            {"type": "hourly"},
            target={"entity_id": weather},
            blocking=True,
            return_response=True,
        )
    except Exception:  # noqa: BLE001 - callers keep their last good forecast
        _LOGGER.warning("Signal could not read the forecast for %s", weather)
        return None
    rows = ((response or {}).get(weather) or {}).get("forecast")
    return [row for row in rows if isinstance(row, dict)] if isinstance(rows, list) else []


async def async_hourly_forecast(hass: HomeAssistant, weather: str) -> list[dict] | None:
    """Hourly forecast rows, shared by every signal that reads the same weather entity."""

    cache: dict[str, tuple[datetime, Any]] = hass.data.setdefault(DOMAIN, {}).setdefault(
        _FORECAST_CACHE, {}
    )
    now = dt_util.utcnow()
    hit = cache.get(weather)
    if hit is not None and now - hit[0] < FORECAST_REUSE:
        return await hit[1]
    task = hass.async_create_task(_async_fetch_hourly(hass, weather))
    cache[weather] = (now, task)
    rows = await task
    if rows is None and cache.get(weather, (None, None))[1] is task:
        cache.pop(weather, None)
    return rows


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
        self._stopped = False
        self.missing: list[str] = []
        self.stale: list[str] = []
        self.reason = ""

    def listen(self, update: Any) -> Any:
        self._listeners.append(update)

        def _unsub() -> None:
            if update in self._listeners:
                self._listeners.remove(update)

        return _unsub

    def _notify(self) -> None:
        for update in list(self._listeners):
            try:
                update()
            except Exception:  # noqa: BLE001 - one entity must not stop the signal
                _LOGGER.exception("Signal %s could not update an entity", self.subentry_id)
        self._schedule_save()

    def _schedule_save(self) -> None:
        return None

    def async_start(self) -> Any:
        self.hass.async_create_task(self._async_start())
        return self._stop

    async def _async_start(self) -> None:
        raise NotImplementedError

    def _watch(self, entities: list[str], refresh: Any, poll: Any) -> None:
        """Refresh on source changes, re-check freshness each minute, poll the forecast."""

        @callback
        def _state_changed(_event: Event[EventStateChangedData]) -> None:
            refresh(dt_util.now())

        @callback
        def _tick(now: datetime) -> None:
            refresh(dt_util.as_local(now), observe=False)

        self._unsubs.append(async_track_state_change_event(self.hass, entities, _state_changed))
        self._unsubs.append(async_track_time_interval(self.hass, _tick, TICK_EVERY))
        self._unsubs.append(async_track_time_interval(self.hass, poll, FORECAST_EVERY))

    def _stop(self) -> None:
        self._stopped = True
        for unsub in self._unsubs:
            unsub()
        self._unsubs.clear()
        if self._save_unsub is not None:
            self._save_unsub()
            self._save_unsub = None

    def _set_issue(self) -> None:
        self._set_one_issue("signal_source_missing", self.missing)
        self._set_one_issue("signal_source_stale", self.stale)

    def _set_one_issue(self, key: str, entities: list[str]) -> None:
        issue_id = f"{key}_{self.subentry_id}"
        if not entities:
            ir.async_delete_issue(self.hass, DOMAIN, issue_id)
            return
        ir.async_create_issue(
            self.hass,
            DOMAIN,
            issue_id,
            is_fixable=False,
            severity=ir.IssueSeverity.WARNING,
            translation_key=key,
            translation_placeholders={
                "entities": ", ".join(entities),
                "hours": f"{STATION_STALE.total_seconds() / 3600:g}",
            },
        )

    def diagnostics(self) -> dict[str, Any]:
        sources = {}
        for key, value in self.data.items():
            if not key.endswith("_entity") or not isinstance(value, str):
                continue
            state = self.hass.states.get(value)
            sources[key] = None if state is None else {
                "entity_id": value,
                "state": state.state,
                "unit": state.attributes.get("unit_of_measurement"),
                "last_reported": None
                if _reported_at(state) is None
                else _reported_at(state).isoformat(),
            }
        return {
            "data": dict(self.data),
            "missing": self.missing,
            "stale": self.stale,
            "reason": self.reason,
            "sources": sources,
        }


def _get_runtime(
    hass: HomeAssistant, entry: Any, key: str, subentry_id: str, build: Any
) -> Any:
    runtimes: dict[str, SignalRuntime] = hass.data.setdefault(DOMAIN, {}).setdefault(key, {})
    runtime = runtimes.get(subentry_id)
    if runtime is None:
        runtime = build()
        runtimes[subentry_id] = runtime
        entry.async_on_unload(runtime.async_start())

        def _drop() -> None:
            runtimes.pop(subentry_id, None)

        entry.async_on_unload(_drop)
    return runtime


def async_get_wind_runtime(
    hass: HomeAssistant, entry: Any, subentry_id: str, data: dict[str, Any]
) -> WindSignalRuntime:
    """Return the shared runtime for a wind entry."""

    return _get_runtime(
        hass, entry, WIND_RUNTIMES, subentry_id, lambda: WindSignalRuntime(hass, subentry_id, data)
    )


def async_get_threshold_runtime(
    hass: HomeAssistant,
    entry: Any,
    subentry_id: str,
    data: dict[str, Any],
    kind: str,
) -> ThresholdRuntime:
    """Return the shared runtime for a temperature or bad-weather entry."""

    return _get_runtime(
        hass,
        entry,
        THRESHOLD_RUNTIMES,
        subentry_id,
        lambda: ThresholdRuntime(hass, subentry_id, data, kind),
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
        self._unit = "mph"
        self._forecast_unit: str | None = None

    @property
    def unit(self) -> str:
        """The gust sensor's unit. Every Wind speed and line uses it."""

        gust_state = self.hass.states.get(str(self.data.get("gust_entity", "")))
        unit = None if gust_state is None else gust_state.attributes.get("unit_of_measurement")
        if unit:
            self._unit = str(unit)
        return self._unit

    async def _async_start(self) -> None:
        stored = await self._store.async_load()
        if self._stopped:
            return
        if isinstance(stored, dict):
            self.engine.import_state(stored)
        self._refresh(dt_util.now())
        await self._async_poll_forecast()
        if self._stopped:
            return
        gust = self.data["gust_entity"]
        heartbeat = self.data.get("heartbeat_entity") or gust
        watched = {gust, heartbeat, self.data["weather_entity"]}
        self._watch(sorted(watched), self._refresh, self._async_poll_forecast)

    def _schedule_save(self) -> None:
        if self._save_unsub is not None or self._stopped:
            return

        @callback
        def _save(_now: datetime) -> None:
            self._save_unsub = None
            self.hass.async_create_task(self._store.async_save(self.engine.export_state()))

        self._save_unsub = async_call_later(self.hass, SAVE_DELAY.total_seconds(), _save)

    def _refresh(self, now: datetime, observe: bool = True) -> None:
        if self._stopped:
            return
        gust_entity = self.data["gust_entity"]
        heartbeat_entity = self.data.get("heartbeat_entity") or gust_entity
        self.missing = [
            entity
            for entity in (gust_entity, self.data["weather_entity"])
            if self.hass.states.get(entity) is None
        ]
        heartbeat = self.hass.states.get(heartbeat_entity)
        self.stale = [heartbeat_entity] if _is_stale(heartbeat, now) else []
        self._set_issue()
        gust = _float_state(self.hass.states.get(gust_entity))
        if observe and gust is not None:
            self.engine.observe_gust(now, gust)
        station_fresh = _is_fresh(heartbeat, now) and not self.missing
        snapshot = self.engine.update(now, gust, station_fresh)
        self.reason = describe_wind(snapshot, self.engine.options, self.unit)
        self._notify()
        if self._forecast_unit is not None and self._forecast_unit != self.unit:
            # The gust sensor came online in another unit; re-read the forecast in it.
            self._forecast_unit = self.unit
            self.hass.async_create_task(self._async_poll_forecast())

    async def _async_poll_forecast(self, _now: datetime | None = None) -> None:
        weather = self.data["weather_entity"]
        state = self.hass.states.get(weather)
        if state is None:
            self._refresh(dt_util.now())
            return
        unit = self.unit
        self._forecast_unit = unit
        source_unit = state.attributes.get("wind_speed_unit")
        rows = await async_hourly_forecast(self.hass, weather)
        if self._stopped:
            return
        now = dt_util.now()
        if rows is None:
            self._refresh(now)
            return
        hourly: list[float] = []
        stamps: list[datetime | None] = []
        for row in rows:
            speed = row.get("wind_speed")
            if not isinstance(speed, (int, float)):
                continue
            stamp = _stamp(row)
            if stamp is not None and (stamp + HOUR <= now or stamp - now > FORECAST_AHEAD):
                continue
            hourly.append(_convert(SpeedConverter, float(speed), source_unit, unit))
            stamps.append(stamp)
        sustained = None
        attr = state.attributes.get("wind_speed")
        if isinstance(attr, (int, float)):
            sustained = _convert(SpeedConverter, float(attr), source_unit, unit)
        known = [stamp for stamp in stamps if stamp is not None]
        self.engine.set_forecast(
            now, sustained, hourly, known if len(known) == len(stamps) else None
        )
        self._refresh(now)

    def diagnostics(self) -> dict[str, Any]:
        snapshot = self.engine.snapshot
        return {
            **super().diagnostics(),
            "unit": self.unit,
            "engine": self.engine.export_state(),
            "snapshot": {
                key: value.isoformat() if isinstance(value, datetime) else value
                for key, value in vars(snapshot).items()
            },
        }


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
        self.hot_at: datetime | None = None
        self.cold_at: datetime | None = None
        self.next_bad_at: datetime | None = None
        self.held_until: datetime | None = None
        self._last_on_at: datetime | None = None
        self._rows: list[tuple[datetime | None, float | None, str | None]] = []
        self._rain = RainTracker()

    async def _async_start(self) -> None:
        await self._async_poll_forecast()
        if self._stopped:
            return
        watched = [self.data["weather_entity"]]
        station = self.data.get("station_entity")
        if isinstance(station, str) and station:
            watched.append(station)
        self._watch(watched, self._refresh, self._async_poll_forecast)

    def _line(self, key: str, fallback: float) -> float:
        value = self.data.get(key, fallback)
        return float(value) if isinstance(value, (int, float)) else fallback

    def _conditions(self) -> list[str]:
        raw = self.data.get("storm_conditions") or STORM_DEFAULT
        return [str(item) for item in raw]

    def temperature_unit(self) -> str | None:
        """Lines and the published Temperature use the forecast unit, else the station's."""

        weather = self.hass.states.get(self.data["weather_entity"])
        unit = None if weather is None else weather.attributes.get("temperature_unit")
        if unit:
            return str(unit)
        station_id = self.data.get("station_entity")
        station = self.hass.states.get(station_id) if isinstance(station_id, str) else None
        unit = None if station is None else station.attributes.get("unit_of_measurement")
        return str(unit) if unit else None

    def margin(self) -> float:
        return self._line("clear_margin", default_margin(self.temperature_unit()))

    def hold(self) -> timedelta:
        return timedelta(minutes=self._line("hold_minutes", HOLD_MINUTES))

    def _window(self, now: datetime) -> list[tuple[datetime | None, float | None, str | None]]:
        """Forecast hours that have not ended and start within the next 2 hours."""

        rows = []
        for row in self._rows:
            stamp = row[0]
            if stamp is None:
                if len(rows) < 2:
                    rows.append(row)
                continue
            if stamp + HOUR > now and stamp - now <= _FORECAST_WINDOW:
                rows.append(row)
        return rows

    def _first(self, now: datetime, matches: Any) -> datetime | None:
        for stamp, temp, condition in self._rows:
            if stamp is not None and stamp + HOUR > now and matches(temp, condition):
                return stamp
        return None

    def _refresh(self, now: datetime, observe: bool = True) -> None:
        if self._stopped:
            return
        weather = self.data["weather_entity"]
        station_id = self.data.get("station_entity")
        has_station = isinstance(station_id, str) and bool(station_id)
        station = self.hass.states.get(station_id) if has_station else None
        self.missing = [weather] if self.hass.states.get(weather) is None else []
        if has_station and station is None:
            self.missing.append(station_id)
        self.stale = [station_id] if has_station and _is_stale(station, now) else []
        self._set_issue()

        self.station_fresh = _is_fresh(station, now)
        forecast_state = self.hass.states.get(weather)
        window = self._window(now)
        if self.kind == "temperature":
            self._refresh_temperature(now, station, forecast_state, window)
        else:
            self._refresh_bad_weather(now, station, has_station, forecast_state, window)
        self._notify()

    def _refresh_temperature(
        self,
        now: datetime,
        station: State | None,
        forecast_state: State | None,
        window: list[tuple[datetime | None, float | None, str | None]],
    ) -> None:
        unit = self.temperature_unit()
        self.local_temperature = _float_state(station)
        if self.local_temperature is not None and station is not None:
            # Lines and forecast use the forecast unit; bring the station into it.
            self.local_temperature = _convert(
                TemperatureConverter,
                self.local_temperature,
                station.attributes.get("unit_of_measurement"),
                unit,
            )
        raw = None if forecast_state is None else forecast_state.attributes.get("temperature")
        self.forecast_temperature = float(raw) if isinstance(raw, (int, float)) else None
        temps = [self.forecast_temperature] if self.forecast_temperature is not None else []
        temps.extend(temp for _stamp, temp, _condition in window if temp is not None)
        high = max(temps) if temps else None
        low = min(temps) if temps else None
        hot_line = self._line("hot_threshold", 90)
        cold_line = self._line("cold_threshold", 32)
        margin = self.margin()
        merged = merge_temperature(
            local=self.local_temperature,
            local_fresh=self.station_fresh,
            forecast_now=self.forecast_temperature,
            forecast_high=high,
            forecast_low=low,
            hot_line=hot_line,
            cold_line=cold_line,
            previous_hot=self.hot,
            previous_cold=self.cold,
            margin=margin,
        )
        self.temperature = merged.temperature
        self.hot = merged.hot
        self.cold = merged.cold
        self.is_on = self.hot or self.cold
        self.condition = None if forecast_state is None else forecast_state.state
        self.hot_at = self._first(now, lambda temp, _c: temp is not None and temp > hot_line)
        self.cold_at = self._first(now, lambda temp, _c: temp is not None and temp < cold_line)
        self.reason = describe_temperature(
            merged=merged,
            live=self.local_temperature if self.station_fresh else None,
            forecast_high=high,
            forecast_low=low,
            hot_line=hot_line,
            cold_line=cold_line,
            margin=margin,
            unit=unit or "",
        )

    def _refresh_bad_weather(
        self,
        now: datetime,
        station: State | None,
        has_station: bool,
        forecast_state: State | None,
        window: list[tuple[datetime | None, float | None, str | None]],
    ) -> None:
        forecast_condition = None if forecast_state is None else forecast_state.state
        conditions = self._conditions()
        hits = [f"{forecast_condition} now"] if forecast_condition in conditions else []
        for stamp, _temp, condition in window:
            if condition in conditions and stamp is not None:
                hits.append(f"{condition} at {_clock(stamp)}")
        self.forecast_bad = forecast_condition in conditions or any(
            condition in conditions for _stamp, _temp, condition in window
        )
        raining = self._station_reports_rain(station, now)
        self.local_bad = self.station_fresh and raining
        self.condition, raw_on = merge_bad_weather(
            local_bad=self.local_bad,
            forecast_condition=forecast_condition,
            forecast_bad=self.forecast_bad,
        )
        self.is_on, self._last_on_at, self.held_until = apply_hold(
            raw_on, self._last_on_at, now, self.hold()
        )
        # Stable values only: this runs every minute and should not rewrite state each time.
        self.next_bad_at = (
            dt_util.as_local(forecast_state.last_changed)
            if forecast_state is not None and forecast_condition in conditions
            else self._first(now, lambda _t, condition: condition in conditions)
        )
        self.temperature = None
        self.hot = False
        self.cold = False
        self.reason = describe_bad_weather(
            is_on=self.is_on,
            local_bad=self.local_bad,
            station_configured=has_station,
            station_fresh=self.station_fresh,
            forecast_condition=forecast_condition,
            forecast_hits=hits,
            held_until=None if self.held_until is None else _clock(self.held_until),
        )

    async def _async_poll_forecast(self, _now: datetime | None = None) -> None:
        weather = self.data["weather_entity"]
        if self.hass.states.get(weather) is None:
            self._rows = []
            self._refresh(dt_util.now())
            return
        rows = await async_hourly_forecast(self.hass, weather)
        if self._stopped:
            return
        now = dt_util.now()
        if rows is not None:
            parsed = []
            for row in rows:
                stamp = _stamp(row)
                if stamp is not None and stamp - now > FORECAST_AHEAD:
                    continue
                temp = row.get("temperature")
                condition = row.get("condition")
                parsed.append(
                    (
                        stamp,
                        float(temp) if isinstance(temp, (int, float)) else None,
                        condition if isinstance(condition, str) else None,
                    )
                )
            self._rows = parsed
        self._refresh(now)

    def _station_reports_rain(self, state: State | None, now: datetime) -> bool:
        """Wet sensor on, rain rate above 0, or a rain total that rose recently."""

        if state is None or state.state in (STATE_UNKNOWN, STATE_UNAVAILABLE, ""):
            return False
        if state.entity_id.startswith("binary_sensor.") or state.attributes.get("device_class") == "moisture":
            return state.state == "on"
        amount = _float_state(state)
        if _is_rain_rate(state):
            return amount is not None and amount > 0
        self._rain.observe(now, amount)
        return self._rain.raining(now)

    def diagnostics(self) -> dict[str, Any]:
        def iso(value: datetime | None) -> str | None:
            return None if value is None else value.isoformat()

        return {
            **super().diagnostics(),
            "kind": self.kind,
            "is_on": self.is_on,
            "hot": self.hot,
            "cold": self.cold,
            "temperature": self.temperature,
            "local_temperature": self.local_temperature,
            "forecast_temperature": self.forecast_temperature,
            "condition": self.condition,
            "station_fresh": self.station_fresh,
            "local_bad": self.local_bad,
            "forecast_bad": self.forecast_bad,
            "held_until": iso(self.held_until),
            "hot_at": iso(self.hot_at),
            "cold_at": iso(self.cold_at),
            "next_bad_at": iso(self.next_bad_at),
            "rain_total": {"last": self._rain.last, "rose_at": iso(self._rain.rose_at)},
            "forecast_rows": [
                [iso(stamp), temp, condition] for stamp, temp, condition in self._rows
            ],
        }


def _is_rain_rate(state: State) -> bool:
    if state.attributes.get("device_class") == "precipitation_intensity":
        return True
    return "/" in str(state.attributes.get("unit_of_measurement") or "")
