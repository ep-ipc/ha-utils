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
from .logic import WindEngine, WindOptions

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


class ThresholdRuntime(SignalRuntime):
    """On/off signal from one weather entity."""

    def __init__(self, hass: HomeAssistant, subentry_id: str, data: dict[str, Any], kind: str) -> None:
        super().__init__(hass, subentry_id, data)
        self.kind = kind
        self.is_on = False

    def async_start(self) -> Any:
        weather = self.data["weather_entity"]

        @callback
        def _state_changed(_event: Event[EventStateChangedData]) -> None:
            self._refresh()

        self._refresh()
        self._unsubs.append(async_track_state_change_event(self.hass, [weather], _state_changed))
        return self._stop

    def _refresh(self) -> None:
        weather = self.data["weather_entity"]
        state = self.hass.states.get(weather)
        self.missing = [] if state is not None else [weather]
        self._set_issue()
        self.is_on = False if state is None else self._matches(state)
        self._notify()

    def _matches(self, state: State) -> bool:
        if self.kind == "thunderstorm":
            conditions = self.data.get("storm_conditions") or [
                "lightning",
                "lightning-rainy",
                "pouring",
                "rainy",
            ]
            return state.state in conditions
        temperature = state.attributes.get("temperature")
        if not isinstance(temperature, (int, float)):
            return False
        threshold = float(self.data["threshold"])
        if self.kind == "hot_day":
            return float(temperature) > threshold
        return float(temperature) < threshold
