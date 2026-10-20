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
RAIN_RECENT = timedelta(minutes=30)
HOUR = timedelta(hours=1)

# Starting lines in mph and °F. Setup converts them to the house unit system.
WIND_LINES_MPH = {"rise_big": 30.0, "rise_all": 60.0, "fall_all": 45.0, "fall_big": 20.0}
TEMPERATURE_LINES_F = {"hot_threshold": 90.0, "cold_threshold": 32.0}
CLEAR_MARGIN_F = 2.0
CLEAR_MARGIN_C = 1.0
HOLD_MINUTES = 30.0


def default_margin(temperature_unit: str | None) -> float:
    """Hot and Cold clear this far back past their line."""

    return CLEAR_MARGIN_C if temperature_unit == "°C" else CLEAR_MARGIN_F

LINE_ERRORS = {
    "rise_order": "Rise to warning must be above Rise to advisory.",
    "fall_order": "Fall from warning must be above Fall to safe.",
    "advisory_gap": "Fall to safe must be below Rise to advisory.",
    "warning_gap": "Fall from warning must be below Rise to warning.",
    "temperature_order": "Hot above must be higher than Cold below.",
}


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
    advisory_at: datetime | None = None
    warning_at: datetime | None = None


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
    hourly_at: list[datetime] = field(default_factory=list)
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
        stamps: list[datetime] | None = None,
    ) -> None:
        """Store the forecast. Stamps are each hour's start, when the weather entity gives them."""

        self.forecast_at = when
        self.sustained = sustained
        self.hourly = list(hourly)
        self.hourly_at = list(stamps) if stamps and len(stamps) == len(hourly) else []

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

        peak_1h = self._scaled_peak(1, now) if forecast_fresh else None
        peak_2h = self._scaled_peak(2, now) if forecast_fresh else None
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
            advisory_at=self.expected_at(now, self.options.rise_big) if forecast_fresh else None,
            warning_at=self.expected_at(now, self.options.rise_all) if forecast_fresh else None,
        )
        return self.snapshot

    def _rows(self, now: datetime, hours: int | None) -> list[float]:
        """Forecast speeds for hours that have not ended, up to `hours` ahead."""

        if not self.hourly_at:
            return self.hourly if hours is None else self.hourly[:hours]
        end = None if hours is None else now + timedelta(hours=hours)
        return [
            speed
            for stamp, speed in zip(self.hourly_at, self.hourly)
            if stamp + HOUR > now and (end is None or stamp < end)
        ]

    def _scaled_peak(self, hours: int, now: datetime) -> float | None:
        values: list[float] = []
        if self.sustained is not None:
            values.append(self.sustained)
        values.extend(self._rows(now, hours))
        if not values:
            return None
        return max(values) * self.factor

    def expected_at(self, now: datetime, line: float) -> datetime | None:
        """Start of the first forecast hour whose scaled wind reaches `line`."""

        for stamp, speed in zip(self.hourly_at, self.hourly):
            if stamp + HOUR > now and speed * self.factor >= line:
                return stamp
        return None

    def export_state(self) -> dict:
        return {
            "factor": self.factor,
            "level": self.level,
            "sustained": self.sustained,
            "hourly": self.hourly,
            "hourly_at": [stamp.isoformat() for stamp in self.hourly_at],
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
        stamps = [_parse_stamp(value) for value in raw.get("hourly_at", [])]
        self.hourly_at = (
            [stamp for stamp in stamps if stamp is not None]
            if len(stamps) == len(self.hourly) and all(stamps)
            else []
        )
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
    previous_hot: bool = False,
    previous_cold: bool = False,
    margin: float = 0.0,
) -> TemperatureMerge:
    """Prefer a fresh station reading. Forecast can turn hot or cold on, not off.

    Once on, Hot stays on until both readings are at least `margin` below the
    line, and Cold until both are at least `margin` above it.
    """

    live = local if local_fresh else None
    temperature = live if live is not None else forecast_now

    def above(line: float | None) -> bool:
        return line is not None and any(
            value is not None and value > line for value in (live, forecast_high)
        )

    def below(line: float | None) -> bool:
        return line is not None and any(
            value is not None and value < line for value in (live, forecast_low)
        )

    hot = above(hot_line) or (
        previous_hot and hot_line is not None and above(hot_line - margin)
    )
    cold = below(cold_line) or (
        previous_cold and cold_line is not None and below(cold_line + margin)
    )
    return TemperatureMerge(temperature, hot, cold)


def _amount(value: float, unit: str) -> str:
    return f"{round(value, 1):g} {unit}".strip()


def describe_temperature(
    *,
    merged: TemperatureMerge,
    live: float | None,
    forecast_high: float | None,
    forecast_low: float | None,
    hot_line: float,
    cold_line: float,
    margin: float,
    unit: str,
) -> str:
    """One sentence on why Hot and Cold are on or off."""

    def show(value: float) -> str:
        return _amount(value, unit)

    if merged.hot:
        if live is not None and live > hot_line:
            return f"Hot because the station reads {show(live)}, above {show(hot_line)}."
        if forecast_high is not None and forecast_high > hot_line:
            return (
                f"Hot because the forecast reaches {show(forecast_high)} in the next 2 hours, "
                f"above {show(hot_line)}."
            )
        return f"Hot until it is {show(hot_line - margin)} or cooler."
    if merged.cold:
        if live is not None and live < cold_line:
            return f"Cold because the station reads {show(live)}, below {show(cold_line)}."
        if forecast_low is not None and forecast_low < cold_line:
            return (
                f"Cold because the forecast drops to {show(forecast_low)} in the next 2 hours, "
                f"below {show(cold_line)}."
            )
        return f"Cold until it is {show(cold_line + margin)} or warmer."
    if merged.temperature is None:
        return "Unknown. No fresh station reading or forecast."
    return (
        f"Neither. It is {show(merged.temperature)}; "
        f"Hot is above {show(hot_line)} and Cold is below {show(cold_line)}."
    )


def describe_wind(snapshot: WindSnapshot, options: WindOptions, unit: str) -> str:
    """One sentence on why Level is where it is."""

    def show(value: float) -> str:
        return _amount(value, unit)

    risk = snapshot.risk
    calm = snapshot.calm
    if snapshot.level not in LEVELS:
        return "Unknown. No fresh gust or forecast yet."
    if risk is None and calm is None:
        return f"{_cap(snapshot.level)}, kept from before. No fresh gust or forecast."
    local = snapshot.gust_3m if snapshot.station_fresh else None
    source = ""
    if risk is not None:
        from_local = local is not None and round(local, 1) >= risk
        source = " from the local gust" if from_local else " from the forecast"
    if snapshot.level == "warning":
        if risk is not None and risk >= options.rise_all:
            return f"Warning because Risk is {show(risk)}{source}, at or above {show(options.rise_all)}."
        return (
            f"Warning until Calm falls below {show(options.fall_all)}"
            + ("." if calm is None else f"; Calm is {show(calm)}.")
        )
    if snapshot.level == "advisory":
        if risk is not None and risk >= options.rise_big:
            return f"Advisory because Risk is {show(risk)}{source}, at or above {show(options.rise_big)}."
        return (
            f"Advisory until Calm falls below {show(options.fall_big)}"
            + ("." if calm is None else f"; Calm is {show(calm)}.")
        )
    if risk is None:
        return "Safe. Risk is unknown, so it cannot rise."
    return f"Safe. Risk is {show(risk)}{source}, below {show(options.rise_big)}."


def apply_hold(
    raw_on: bool,
    last_on_at: datetime | None,
    now: datetime,
    hold: timedelta,
) -> tuple[bool, datetime | None, datetime | None]:
    """Keep a signal on for `hold` after it was last on. Returns on, last on, and held until."""

    if raw_on:
        return True, now, None
    if last_on_at is not None and hold > timedelta(0) and timedelta(0) <= now - last_on_at < hold:
        return True, last_on_at, last_on_at + hold
    return False, last_on_at, None


def describe_bad_weather(
    *,
    is_on: bool,
    local_bad: bool,
    station_configured: bool,
    station_fresh: bool,
    forecast_condition: str | None,
    forecast_hits: list[str],
    held_until: str | None = None,
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
    if is_on and held_until:
        held = f"On, holding until {held_until} after the last bad weather."
        if not quiet:
            return held
        return held + " " + ". ".join(_cap(part) for part in quiet) + "."
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


@dataclass
class RainTracker:
    """A rain total counts as rain while it rose in the last 30 minutes."""

    last: float | None = None
    rose_at: datetime | None = None

    def observe(self, now: datetime, total: float | None) -> None:
        if total is None:
            return
        if self.last is not None and total > self.last:
            self.rose_at = now
        self.last = total

    def raining(self, now: datetime) -> bool:
        return self.rose_at is not None and timedelta(0) <= now - self.rose_at < RAIN_RECENT


def line_error(values: dict) -> str | None:
    """Key into LINE_ERRORS when the lines would make a signal flap or stick."""

    wind = [values.get(key) for key in ("rise_big", "rise_all", "fall_big", "fall_all")]
    if all(isinstance(value, (int, float)) for value in wind):
        rise_big, rise_all, fall_big, fall_all = (float(value) for value in wind)
        if rise_big >= rise_all:
            return "rise_order"
        if fall_big >= fall_all:
            return "fall_order"
        if fall_big >= rise_big:
            return "advisory_gap"
        if fall_all >= rise_all:
            return "warning_gap"
    hot = values.get("hot_threshold")
    cold = values.get("cold_threshold")
    if isinstance(hot, (int, float)) and isinstance(cold, (int, float)) and cold >= hot:
        return "temperature_order"
    return None


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
            "Watch Level in your own automation, or use the device triggers "
            "(Level became safe / advisory / warning). "
            "Risk raises the latch; Calm lowers it. Reason says why. "
            "advisory_expected_at and warning_expected_at on Level give the first forecast hour "
            "that reaches each rise line. "
            "Set Weather station, Weather forecast, and the four speeds under Configuration. "
            "Missing Risk or Calm never counts as calm."
        ),
        "rules": (
            "Fall to safe < Rise to advisory < Rise to warning, and "
            "Fall to safe < Fall from warning < Rise to warning. "
            "Speeds use the gust sensor's unit; the forecast is converted to it."
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


def temperature_guide_attributes(
    hot: float, cold: float, *, docs: str, margin: float = 0.0
) -> dict[str, str]:
    """Attribute text for the Temperature Guide entity."""

    return {
        "summary": (
            "Live station temperature is preferred when fresh. "
            "Forecast high/low next 2 hours can turn Hot or Cold on early. "
            "Reason says why; hot_expected_at and cold_expected_at on Hot and Cold "
            "give the first forecast hour past each line."
        ),
        "hot_above": f"Hot turns on above {hot:g}.",
        "cold_below": f"Cold turns on below {cold:g}.",
        "hot_clears": f"Hot clears at {hot - margin:g} or cooler.",
        "cold_clears": f"Cold clears at {cold + margin:g} or warmer.",
        "rules": (
            "Cold below must be lower than Hot above. "
            "Station readings are converted to the forecast unit."
        ),
        "docs": docs,
    }


def bad_weather_guide_state() -> str:
    """One-line summary for the Bad weather Guide entity."""

    return "Station rain or forecast storm → On"


def bad_weather_guide_attributes(
    conditions: list[str],
    *,
    docs: str,
    hold_minutes: float = HOLD_MINUTES,
) -> dict[str, object]:
    """Attribute text for the Bad weather Guide entity."""

    return {
        "summary": (
            "Bad weather turns on for live station rain or a matching forecast "
            "condition in the next 2 hours, then stays on for Hold for minutes after "
            "the last one. Condition can stay sunny while On. "
            "A rain total counts as rain while it rose in the last 30 minutes; "
            "a rain rate counts while it is above 0."
        ),
        "hold_minutes": hold_minutes,
        "conditions": conditions,
        "reason": "Read the Reason sensor for the current sentence.",
        "docs": docs,
    }
