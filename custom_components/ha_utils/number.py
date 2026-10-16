"""Hot and cold lines shown on the temperature device page."""

from __future__ import annotations

from homeassistant.components.number import NumberEntity, NumberMode
from homeassistant.config_entries import ConfigEntry, ConfigSubentry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Add the hot and cold thresholds for each temperature entry."""

    for subentry in entry.subentries.values():
        if subentry.subentry_type != "temperature":
            continue
        async_add_entities(
            [
                ThresholdNumber(entry.entry_id, subentry, "hot_threshold", "Hot above", 90),
                ThresholdNumber(entry.entry_id, subentry, "cold_threshold", "Cold below", 32),
            ],
            config_subentry_id=subentry.subentry_id,
        )


class ThresholdNumber(NumberEntity):
    """A temperature line the user can change on the device page."""

    _attr_has_entity_name = True
    _attr_should_poll = False
    _attr_entity_category = EntityCategory.CONFIG
    _attr_mode = NumberMode.BOX
    _attr_native_min_value = -50
    _attr_native_max_value = 150
    _attr_native_step = 1

    def __init__(
        self,
        entry_id: str,
        subentry: ConfigSubentry,
        key: str,
        name: str,
        default: float,
    ) -> None:
        self.entry_id = entry_id
        self.subentry_id = subentry.subentry_id
        self.key = key
        self._default = default
        self._attr_name = name
        self._attr_unique_id = f"{subentry.subentry_id}_{key}"
        self._attr_icon = "mdi:thermometer-high" if key == "hot_threshold" else "mdi:thermometer-low"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, subentry.subentry_id)},
            name=subentry.title,
            manufacturer="HA Utils",
            model="Temperature",
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
