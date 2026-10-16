"""Pure signal math for HA Utils weather utilities.

No Home Assistant imports. The integration runtime feeds measurements in
and reads the snapshot back.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta

LEVELS = ("safe", "big", "all")
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

    if previous == "all":
        if calm is not None and calm < options.fall_big:
            return "safe"
        if calm is not None and calm < options.fall_all:
            return "big"
        return "all"

    if previous == "big":
        if risk is not None and risk >= options.rise_all:
            return "all"
        if calm is not None and calm < options.fall_big:
            return "safe"
        return "big"

    if risk is not None and risk >= options.rise_all:
        return "all"
    if risk is not None and risk >= options.rise_big:
        return "big"
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
