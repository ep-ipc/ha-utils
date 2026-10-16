"""Configuration selectors shown on a signal device page."""

from __future__ import annotations

from homeassistant.components.select import SelectEntity
from homeassistant.config_entries import ConfigEntry, ConfigSubentry
from homeassistant.const import STATE_UNAVAILABLE, STATE_UNKNOWN
from homeassistant.const import EVENT_STATE_CHANGED
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.event import async_call_later
from homeassistant.helpers.entity_registry import EVENT_ENTITY_REGISTRY_UPDATED

from .const import DOMAIN


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Add source pickers for each wind signal."""

    for subentry in entry.subentries.values():
        if subentry.subentry_type != "wind_signal":
            continue
        async_add_entities(
            [
                WindSourceSelect(
                    entry.entry_id,
                    subentry,
                    key="gust_entity",
                    name="Weather station",
                    icon="mdi:weather-windy",
                ),
                WindSourceSelect(
                    entry.entry_id,
                    subentry,
                    key="weather_entity",
                    name="Forecast",
                    icon="mdi:weather-partly-cloudy",
                ),
            ],
            config_subentry_id=subentry.subentry_id,
        )


def _same_device(hass: HomeAssistant, left: str, right: str) -> bool:
    registry = er.async_get(hass)
    left_entry = registry.async_get(left)
    right_entry = registry.async_get(right)
    if left_entry is None or right_entry is None:
        return False
    return bool(left_entry.device_id and left_entry.device_id == right_entry.device_id)


class WindSourceSelect(SelectEntity):
    """Pick the gust sensor or the forecast weather entity."""

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
    ) -> None:
        self.entry_id = entry_id
        self.subentry_id = subentry.subentry_id
        self.key = key
        self._attr_name = name
        self._attr_icon = icon
        self._attr_unique_id = f"{subentry.subentry_id}_{key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, subentry.subentry_id)},
            name=subentry.title,
            manufacturer="HA Utils",
            model="Wind signal",
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
        if self.key == "weather_entity":
            found = [
                state.entity_id
                for state in self.hass.states.async_all("weather")
                if state.state not in (STATE_UNAVAILABLE, STATE_UNKNOWN)
            ]
        else:
            registry = er.async_get(self.hass)
            for state in self.hass.states.async_all("sensor"):
                if state.attributes.get("device_class") != "wind_speed":
                    continue
                registered = registry.async_get(state.entity_id)
                if registered is not None and registered.platform == DOMAIN:
                    continue
                found.append(state.entity_id)
        current = self._current()
        if current and current not in found:
            found.append(current)
        return sorted(set(found))

    @property
    def current_option(self) -> str | None:
        current = self._current()
        if current in self.options:
            return current
        return None

    async def async_select_option(self, option: str) -> None:
        if option not in self.options or option == self._current():
            return
        entry = self.hass.config_entries.async_get_entry(self.entry_id)
        subentry = None if entry is None else entry.subentries.get(self.subentry_id)
        if entry is None or subentry is None:
            return
        data = dict(subentry.data)
        data[self.key] = option
        if self.key == "gust_entity":
            heartbeat = data.get("heartbeat_entity")
            if isinstance(heartbeat, str) and not _same_device(self.hass, heartbeat, option):
                data.pop("heartbeat_entity", None)
        self.hass.config_entries.async_update_subentry(entry, subentry, data=data)
        self.async_write_ha_state()
