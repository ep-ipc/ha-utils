"""Pure signal math for HA Utils weather utilities.

No Home Assistant imports. The integration runtime feeds measurements in
and reads the snapshot back.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta

LEVELS = ("safe", "advisory", "warning")
_LEGACY_LEVELS = {"big": "advisory", "all": "warning"}
FORECAST_STALE = timedelta(hours=3)
GUST_SHORT = timedelta(minutes=3)
GUST_LONG = timedelta(minutes=30)
FACTOR_INTERVAL = timedelta(hours=1)
FACTOR_MIN = 1.0
FACTOR_MAX = 3.0
SAMPLE_GUST_MIN = 5.0
SAMPLE_SUSTAINED_MIN = 8.0


@dataclass(frozen=True)
class WindOptions:
    """Thresholds for one wind signal."""

    rise_big: float = 30.0
    rise_all: float = 60.0
    fall_big: float = 20.0
    fall_all: float = 45.0
    factor_seed: float = 1.4


@dataclass
class WindSnapshot:
    """Values published as entities and diagnostic attributes."""

    level: str
    risk: float | None
    calm: float | None
    factor: float
    sample: float | None
    gust_3m: float | None
    gust_30m: float | None
    forecast_1h: float | None
    forecast_2h: float | None
    forecast_fresh: bool
    station_fresh: bool


def _clamp_factor(value: float) -> float:
    stepped = round(value / 0.05) * 0.05
    return max(FACTOR_MIN, min(FACTOR_MAX, round(stepped, 2)))


def blend_factor(old: float, sample: float) -> float:
    """Move the stored factor 20 percent of the way toward a new sample."""

    return _clamp_factor(0.8 * old + 0.2 * sample)


def factor_sample(
    gust_30m: float | None,
    sustained: float | None,
    station_fresh: bool,
) -> float | None:
    """Gust divided by sustained wind, when both are strong enough to mean it."""

    if not station_fresh or gust_30m is None or sustained is None:
        return None
    if gust_30m < SAMPLE_GUST_MIN or sustained < SAMPLE_SUSTAINED_MIN:
        return None
    return _clamp_factor(gust_30m / sustained)


def _window_max(
    samples: list[tuple[datetime, float]],
    now: datetime,
    window: timedelta,
) -> float | None:
    cutoff = now - window
    values = [value for stamp, value in samples if stamp >= cutoff]
    if not values:
        return None
    return max(values)


def _local(current: float | None, envelope: float | None, fresh: bool) -> float | None:
    if not fresh or current is None:
        return None
    if envelope is None:
        return current
    return max(current, envelope)


def _highest(*values: float | None) -> float | None:
    present = [value for value in values if value is not None]
    if not present:
        return None
    return round(max(present), 1)


def latch_level(
    previous: str,
    risk: float | None,
    calm: float | None,
    options: WindOptions,
) -> str:
    """Rise on risk and fall on calm. Missing numbers never count as calm."""

    if risk is None and calm is None:
        return previous if previous in LEVELS else "unknown"

    previous = _LEGACY_LEVELS.get(previous, previous)

    if previous == "warning":
        if calm is not None and calm < options.fall_big:
            return "safe"
        if calm is not None and calm < options.fall_all:
            return "advisory"
        return "warning"

    if previous == "advisory":
        if risk is not None and risk >= options.rise_all:
            return "warning"
        if calm is not None and calm < options.fall_big:
            return "safe"
        return "advisory"

    if risk is not None and risk >= options.rise_all:
        return "warning"
    if risk is not None and risk >= options.rise_big:
        return "advisory"
    return "safe"


@dataclass
class WindEngine:
    """Rolling gust windows, forecast scale, and the latched level."""

    options: WindOptions = field(default_factory=WindOptions)
    samples: list[tuple[datetime, float]] = field(default_factory=list)
    factor: float = 1.4
    level: str = "unknown"
    sustained: float | None = None
    hourly: list[float] = field(default_factory=list)
    forecast_at: datetime | None = None
    last_factor_step: datetime | None = None
    snapshot: WindSnapshot = field(init=False)

    def __post_init__(self) -> None:
        self.factor = _clamp_factor(self.options.factor_seed)
        self.snapshot = self._empty_snapshot()

    def _empty_snapshot(self) -> WindSnapshot:
        return WindSnapshot(
            level=self.level,
            risk=None,
            calm=None,
            factor=self.factor,
            sample=None,
            gust_3m=None,
            gust_30m=None,
            forecast_1h=None,
            forecast_2h=None,
            forecast_fresh=False,
            station_fresh=False,
        )

    def observe_gust(self, when: datetime, value: float) -> None:
        self.samples.append((when, value))
        cutoff = when - GUST_LONG
        self.samples = [(stamp, gust) for stamp, gust in self.samples if stamp >= cutoff]

    def set_forecast(
        self,
        when: datetime,
        sustained: float | None,
        hourly: list[float],
    ) -> None:
        self.forecast_at = when
        self.sustained = sustained
        self.hourly = list(hourly)

    def update(self, now: datetime, gust: float | None, station_fresh: bool) -> WindSnapshot:
        """Recompute the snapshot. A factor step happens at most once an hour."""

        gust_3m = _window_max(self.samples, now, GUST_SHORT)
        gust_30m = _window_max(self.samples, now, GUST_LONG)
        local_3m = _local(gust, gust_3m, station_fresh)
        local_30m = _local(gust, gust_30m, station_fresh)
        forecast_fresh = (
            self.forecast_at is not None
            and timedelta(0) <= now - self.forecast_at < FORECAST_STALE
        )
        sample = factor_sample(
            local_30m,
            self.sustained if forecast_fresh else None,
            station_fresh,
        )
        if sample is not None and (
            self.last_factor_step is None
            or now - self.last_factor_step >= FACTOR_INTERVAL
        ):
            self.factor = blend_factor(self.factor, sample)
            self.last_factor_step = now

        peak_1h = self._scaled_peak(1) if forecast_fresh else None
        peak_2h = self._scaled_peak(2) if forecast_fresh else None
        risk = _highest(local_3m, peak_2h)
        calm = _highest(local_30m, peak_1h)
        self.level = latch_level(self.level, risk, calm, self.options)
        self.snapshot = WindSnapshot(
            level=self.level,
            risk=risk,
            calm=calm,
            factor=self.factor,
            sample=sample,
            gust_3m=gust_3m if station_fresh else local_3m,
            gust_30m=gust_30m if station_fresh else local_30m,
            forecast_1h=peak_1h,
            forecast_2h=peak_2h,
            forecast_fresh=forecast_fresh,
            station_fresh=station_fresh,
        )
        return self.snapshot

    def _scaled_peak(self, hours: int) -> float | None:
        values: list[float] = []
        if self.sustained is not None:
            values.append(self.sustained)
        values.extend(self.hourly[:hours])
        if not values:
            return None
        return max(values) * self.factor

    def export_state(self) -> dict:
        return {
            "factor": self.factor,
            "level": self.level,
            "sustained": self.sustained,
            "hourly": self.hourly,
            "forecast_at": None if self.forecast_at is None else self.forecast_at.isoformat(),
            "last_factor_step": None
            if self.last_factor_step is None
            else self.last_factor_step.isoformat(),
            "samples": [
                [stamp.isoformat(), value] for stamp, value in self.samples
            ],
        }

    def import_state(self, raw: dict) -> None:
        self.factor = _clamp_factor(float(raw.get("factor", self.factor)))
        level = raw.get("level", self.level)
        level = _LEGACY_LEVELS.get(str(level), level)
        self.level = level if level in LEVELS or level == "unknown" else "unknown"
        sustained = raw.get("sustained")
        self.sustained = None if sustained is None else float(sustained)
        self.hourly = [float(value) for value in raw.get("hourly", [])]
        self.forecast_at = _parse_stamp(raw.get("forecast_at"))
        self.last_factor_step = _parse_stamp(raw.get("last_factor_step"))
        self.samples = []
        for stamp, value in raw.get("samples", []):
            parsed = _parse_stamp(stamp)
            if parsed is not None:
                self.samples.append((parsed, float(value)))


@dataclass(frozen=True)
class TemperatureMerge:
    """Published temperature plus the hot and cold flags."""

    temperature: float | None
    hot: bool
    cold: bool


def merge_temperature(
    *,
    local: float | None,
    local_fresh: bool,
    forecast_now: float | None,
    forecast_high: float | None,
    forecast_low: float | None,
    hot_line: float | None,
    cold_line: float | None,
) -> TemperatureMerge:
    """Prefer a fresh station reading. Forecast can turn hot or cold on, not off."""

    temperature = local if local_fresh and local is not None else forecast_now
    hot = bool(
        (local_fresh and local is not None and hot_line is not None and local > hot_line)
        or (forecast_high is not None and hot_line is not None and forecast_high > hot_line)
    )
    cold = bool(
        (local_fresh and local is not None and cold_line is not None and local < cold_line)
        or (forecast_low is not None and cold_line is not None and forecast_low < cold_line)
    )
    return TemperatureMerge(temperature, hot, cold)


def describe_bad_weather(
    *,
    is_on: bool,
    local_bad: bool,
    station_configured: bool,
    station_fresh: bool,
    forecast_condition: str | None,
    forecast_hits: list[str],
) -> str:
    """One sentence a person can read in the activity log."""

    station = _station_clause(local_bad, station_configured, station_fresh)
    forecast = None
    if forecast_hits:
        forecast = "the forecast is " + ", ".join(forecast_hits)
    elif forecast_condition:
        forecast = f"the forecast is {forecast_condition}"
    causes = [part for part in (station if local_bad else None, forecast if forecast_hits else None) if part]
    if is_on and causes:
        sentence = "On because " + " and ".join(causes) + "."
        if not local_bad and station:
            sentence += " " + _cap(station) + "."
        return sentence
    quiet = [part for part in (station, forecast) if part]
    if not quiet:
        return "Off."
    return "Off. " + ". ".join(_cap(part) for part in quiet) + "."


def _station_clause(local_bad: bool, station_configured: bool, station_fresh: bool) -> str | None:
    if not station_configured:
        return None
    if local_bad:
        return "the station reports rain"
    if not station_fresh:
        return "the station has not reported in the last 15 minutes"
    return "the station is dry"


def _cap(text: str) -> str:
    return text[0].upper() + text[1:]


def merge_bad_weather(
    *,
    local_bad: bool,
    forecast_condition: str | None,
    forecast_bad: bool,
) -> tuple[str | None, bool]:
    """Station rain and a bad forecast each turn the signal on."""

    if local_bad and not forecast_bad:
        return "rainy", True
    return forecast_condition, bool(local_bad or forecast_bad)


def _parse_stamp(value: object) -> datetime | None:
    if not isinstance(value, str) or not value:
        return None
    return datetime.fromisoformat(value)


def wind_guide_state(
    advisory: float,
    warning: float,
    fall_warning: float,
    fall_safe: float,
    unit: str,
) -> str:
    """One-line rise and fall ladders for the Wind Guide entity."""

    return (
        f"↑ safe → advisory ({advisory:g} {unit}) → warning ({warning:g} {unit}) · "
        f"↓ warning → advisory (<{fall_warning:g} {unit}) → safe (<{fall_safe:g} {unit})"
    )


def wind_guide_attributes(
    advisory: float,
    warning: float,
    fall_warning: float,
    fall_safe: float,
    unit: str,
    *,
    docs: str,
) -> dict[str, str]:
    """Attribute text for the Wind Guide entity."""

    return {
        "how_to_use": (
            "Watch Level in your own automation. "
            "Risk raises the latch; Calm lowers it. "
            "Set Weather station, Weather forecast, and the four speeds under Configuration. "
            "Missing Risk or Calm never counts as calm."
        ),
        "rise": (
            f"safe → advisory when Risk ≥ {advisory:g} {unit} → "
            f"warning when Risk ≥ {warning:g} {unit}"
        ),
        "fall": (
            f"warning → advisory when Calm < {fall_warning:g} {unit} → "
            f"safe when Calm < {fall_safe:g} {unit}"
        ),
        "rise_to_advisory": (
            f"When Risk reaches {advisory:g} {unit}, Level becomes advisory."
        ),
        "rise_to_warning": (
            f"When Risk reaches {warning:g} {unit}, Level becomes warning."
        ),
        "fall_from_warning": (
            f"When Calm falls below {fall_warning:g} {unit}, "
            "Level leaves warning for advisory."
        ),
        "fall_to_safe": (
            f"When Calm falls below {fall_safe:g} {unit}, Level becomes safe."
        ),
        "docs": docs,
    }


def temperature_guide_state(hot: float, cold: float) -> str:
    """One-line Hot/Cold summary for the Temperature Guide entity."""

    return f"Cold below {cold:g} · Hot above {hot:g}"


def temperature_guide_attributes(hot: float, cold: float, *, docs: str) -> dict[str, str]:
    """Attribute text for the Temperature Guide entity."""

    return {
        "summary": (
            "Live station temperature is preferred when fresh. "
            "Forecast high/low next 2 hours can turn Hot or Cold on early."
        ),
        "hot_above": f"Hot turns on above {hot:g}.",
        "cold_below": f"Cold turns on below {cold:g}.",
        "docs": docs,
    }


def bad_weather_guide_state() -> str:
    """One-line summary for the Bad weather Guide entity."""

    return "Station rain or forecast storm → On"


def bad_weather_guide_attributes(
    conditions: list[str],
    *,
    docs: str,
) -> dict[str, object]:
    """Attribute text for the Bad weather Guide entity."""

    return {
        "summary": (
            "Bad weather turns on for live station rain or a matching forecast "
            "condition in the next 2 hours. Condition can stay sunny while On."
        ),
        "conditions": conditions,
        "reason": "Read the Reason sensor for the current sentence.",
        "docs": docs,
    }
