"""Threshold lines shown on signal device pages."""

from __future__ import annotations

from homeassistant.components.number import NumberEntity, NumberMode
from homeassistant.config_entries import ConfigEntry, ConfigSubentry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .device_meta import signal_device_info

_TEMPERATURE = (
    ("hot_threshold", "Hot above", 90, "mdi:thermometer-high"),
    ("cold_threshold", "Cold below", 32, "mdi:thermometer-low"),
)
_WIND = (
    ("rise_big", "Rise to advisory", 30, "mdi:arrow-up-bold"),
    ("rise_all", "Rise to warning", 60, "mdi:arrow-up-bold-outline"),
    ("fall_all", "Fall from warning", 45, "mdi:arrow-down-bold-outline"),
    ("fall_big", "Fall to safe", 20, "mdi:arrow-down-bold"),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Add configurable lines for temperature and wind entries."""

    for subentry in entry.subentries.values():
        if subentry.subentry_type == "temperature":
            async_add_entities(
                [
                    ThresholdNumber(
                        entry.entry_id,
                        subentry,
                        key=key,
                        name=name,
                        default=default,
                        icon=icon,
                        model="Temperature",
                        doc="temperature",
                        unit_kind="temperature",
                        minimum=-50,
                        maximum=150,
                    )
                    for key, name, default, icon in _TEMPERATURE
                ],
                config_subentry_id=subentry.subentry_id,
            )
        elif subentry.subentry_type == "wind_signal":
            async_add_entities(
                [
                    ThresholdNumber(
                        entry.entry_id,
                        subentry,
                        key=key,
                        name=name,
                        default=default,
                        icon=icon,
                        model="Wind",
                        doc="wind",
                        unit_kind="wind",
                        minimum=0,
                        maximum=150,
                    )
                    for key, name, default, icon in _WIND
                ],
                config_subentry_id=subentry.subentry_id,
            )


class ThresholdNumber(NumberEntity):
    """A line the user can change on the device page."""

    _attr_has_entity_name = True
    _attr_should_poll = False
    _attr_entity_category = EntityCategory.CONFIG
    _attr_mode = NumberMode.BOX
    _attr_native_step = 1

    def __init__(
        self,
        entry_id: str,
        subentry: ConfigSubentry,
        *,
        key: str,
        name: str,
        default: float,
        icon: str,
        model: str,
        doc: str,
        unit_kind: str,
        minimum: float,
        maximum: float,
    ) -> None:
        self.entry_id = entry_id
        self.subentry_id = subentry.subentry_id
        self.key = key
        self._default = default
        self._unit_kind = unit_kind
        self._attr_name = name
        self._attr_icon = icon
        self._attr_unique_id = f"{subentry.subentry_id}_{key}"
        self._attr_native_min_value = minimum
        self._attr_native_max_value = maximum
        self._attr_device_info = signal_device_info(
            subentry.subentry_id, subentry.title, model, doc
        )

    def _subentry(self) -> ConfigSubentry | None:
        entry = self.hass.config_entries.async_get_entry(self.entry_id)
        if entry is None:
            return None
        return entry.subentries.get(self.subentry_id)

    @property
    def native_value(self) -> float:
        subentry = self._subentry()
        if subentry is None:
            return self._default
        value = subentry.data.get(self.key, self._default)
        return float(value) if isinstance(value, (int, float)) else self._default

    @property
    def native_unit_of_measurement(self) -> str | None:
        subentry = self._subentry()
        if subentry is None:
            return None
        if self._unit_kind == "wind":
            gust_id = subentry.data.get("gust_entity")
            gust = None if not isinstance(gust_id, str) else self.hass.states.get(gust_id)
            unit = None if gust is None else gust.attributes.get("unit_of_measurement")
            return str(unit) if unit else "mph"
        weather_id = subentry.data.get("weather_entity")
        weather = None if not isinstance(weather_id, str) else self.hass.states.get(weather_id)
        unit = None if weather is None else weather.attributes.get("temperature_unit")
        if unit:
            return str(unit)
        station_id = subentry.data.get("station_entity")
        station = None if not isinstance(station_id, str) else self.hass.states.get(station_id)
        unit = None if station is None else station.attributes.get("unit_of_measurement")
        return str(unit) if unit else None

    async def async_set_native_value(self, value: float) -> None:
        entry = self.hass.config_entries.async_get_entry(self.entry_id)
        subentry = None if entry is None else entry.subentries.get(self.subentry_id)
        if entry is None or subentry is None or float(value) == self.native_value:
            return
        data = dict(subentry.data)
        data[self.key] = float(value)
        self.hass.config_entries.async_update_subentry(entry, subentry, data=data)
        self.async_write_ha_state()
