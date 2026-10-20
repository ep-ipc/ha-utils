"""Configuration selectors shown on a signal device page."""

from __future__ import annotations

from homeassistant.components.select import SelectEntity
from homeassistant.config_entries import ConfigEntry, ConfigSubentry
from homeassistant.const import STATE_UNAVAILABLE, STATE_UNKNOWN
from homeassistant.const import EVENT_STATE_CHANGED
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.event import async_call_later
from homeassistant.helpers.entity_registry import EVENT_ENTITY_REGISTRY_UPDATED

from .const import DOMAIN
from .device_meta import signal_device_info


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Add source pickers on each signal device page."""

    for subentry in entry.subentries.values():
        if subentry.subentry_type == "wind_signal":
            entities = [
                SourceSelect(
                    entry.entry_id,
                    subentry,
                    key="gust_entity",
                    name="Weather station",
                    icon="mdi:weather-windy",
                    model="Wind",
                    doc="wind",
                    choices="wind",
                ),
                SourceSelect(
                    entry.entry_id,
                    subentry,
                    key="weather_entity",
                    name="Weather forecast",
                    icon="mdi:weather-partly-cloudy",
                    model="Wind",
                    doc="wind",
                    choices="weather",
                ),
            ]
        elif subentry.subentry_type == "temperature":
            entities = [
                SourceSelect(
                    entry.entry_id,
                    subentry,
                    key="station_entity",
                    name="Weather station",
                    icon="mdi:thermometer",
                    model="Temperature",
                    doc="temperature",
                    choices="temperature",
                    allow_none=True,
                ),
                SourceSelect(
                    entry.entry_id,
                    subentry,
                    key="weather_entity",
                    name="Weather forecast",
                    icon="mdi:weather-partly-cloudy",
                    model="Temperature",
                    doc="temperature",
                    choices="weather",
                ),
            ]
        elif subentry.subentry_type == "bad_weather":
            entities = [
                SourceSelect(
                    entry.entry_id,
                    subentry,
                    key="station_entity",
                    name="Weather station",
                    icon="mdi:weather-rainy",
                    model="Bad weather",
                    doc="bad-weather",
                    choices="rain",
                    allow_none=True,
                ),
                SourceSelect(
                    entry.entry_id,
                    subentry,
                    key="weather_entity",
                    name="Weather forecast",
                    icon="mdi:weather-partly-cloudy",
                    model="Bad weather",
                    doc="bad-weather",
                    choices="weather",
                ),
            ]
        else:
            continue
        async_add_entities(entities, config_subentry_id=subentry.subentry_id)


def _same_device(hass: HomeAssistant, left: str, right: str) -> bool:
    registry = er.async_get(hass)
    left_entry = registry.async_get(left)
    right_entry = registry.async_get(right)
    if left_entry is None or right_entry is None:
        return False
    return bool(left_entry.device_id and left_entry.device_id == right_entry.device_id)


class SourceSelect(SelectEntity):
    """Pick a gust sensor or a weather entity on the device page."""

    _attr_has_entity_name = True
    _attr_should_poll = False
    _attr_entity_category = EntityCategory.CONFIG

    def __init__(
        self,
        entry_id: str,
        subentry: ConfigSubentry,
        *,
        key: str,
        name: str,
        icon: str,
        model: str,
        doc: str,
        choices: str,
        allow_none: bool = False,
    ) -> None:
        self.entry_id = entry_id
        self.subentry_id = subentry.subentry_id
        self.key = key
        self.choices = choices
        self.allow_none = allow_none
        self._attr_name = name
        self._attr_icon = icon
        self._attr_unique_id = f"{subentry.subentry_id}_{key}"
        self._attr_device_info = signal_device_info(
            subentry.subentry_id, subentry.title, model, doc
        )

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        self._refresh_unsub = None
        self._published = self.options

        @callback
        def _schedule(_event) -> None:
            if self._refresh_unsub is not None:
                return
            self._refresh_unsub = async_call_later(self.hass, 2, _publish)

        @callback
        def _publish(_now) -> None:
            self._refresh_unsub = None
            current = self.options
            if current == self._published:
                return
            self._published = current
            self.async_write_ha_state()

        def _cancel_pending() -> None:
            if self._refresh_unsub is not None:
                self._refresh_unsub()
                self._refresh_unsub = None

        self.async_on_remove(_cancel_pending)
        self.async_on_remove(
            self.hass.bus.async_listen(EVENT_ENTITY_REGISTRY_UPDATED, _schedule)
        )
        self.async_on_remove(self.hass.bus.async_listen(EVENT_STATE_CHANGED, _schedule))

    def _subentry(self) -> ConfigSubentry | None:
        entry = self.hass.config_entries.async_get_entry(self.entry_id)
        if entry is None:
            return None
        return entry.subentries.get(self.subentry_id)

    def _current(self) -> str | None:
        subentry = self._subentry()
        if subentry is None:
            return None
        value = subentry.data.get(self.key)
        return str(value) if value else None

    @property
    def options(self) -> list[str]:
        found: list[str] = []
        if self.choices == "weather":
            found = [
                state.entity_id
                for state in self.hass.states.async_all("weather")
                if state.state not in (STATE_UNAVAILABLE, STATE_UNKNOWN)
            ]
        else:
            registry = er.async_get(self.hass)
            domains = ("binary_sensor", "sensor") if self.choices == "rain" else ("sensor",)
            wanted = {
                "wind": "wind_speed",
                "temperature": "temperature",
            }.get(self.choices)
            for domain in domains:
                for state in self.hass.states.async_all(domain):
                    device_class = state.attributes.get("device_class")
                    if self.choices == "rain":
                        if device_class not in ("moisture", "precipitation", "precipitation_intensity"):
                            continue
                    elif device_class != wanted:
                        continue
                    registered = registry.async_get(state.entity_id)
                    if registered is not None and registered.platform == DOMAIN:
                        continue
                    found.append(state.entity_id)
        current = self._current()
        if current and current not in found:
            found.append(current)
        choices = sorted(set(found))
        if self.allow_none:
            return ["none", *choices]
        return choices

    @property
    def current_option(self) -> str | None:
        current = self._current()
        if current in self.options:
            return current
        if self.allow_none and current is None:
            return "none"
        return None

    async def async_select_option(self, option: str) -> None:
        current = self._current()
        if option not in self.options:
            return
        if option == "none":
            if current is None:
                return
        elif option == current:
            return
        entry = self.hass.config_entries.async_get_entry(self.entry_id)
        subentry = None if entry is None else entry.subentries.get(self.subentry_id)
        if entry is None or subentry is None:
            return
        data = dict(subentry.data)
        if option == "none":
            data.pop(self.key, None)
        else:
            data[self.key] = option
        if self.key == "gust_entity":
            heartbeat = data.get("heartbeat_entity")
            if isinstance(heartbeat, str) and not _same_device(self.hass, heartbeat, option):
                data.pop("heartbeat_entity", None)
        self.hass.config_entries.async_update_subentry(entry, subentry, data=data)
        self.async_write_ha_state()
