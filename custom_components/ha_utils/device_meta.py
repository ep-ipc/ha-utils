"""Shared device registry metadata for signal entries."""

from __future__ import annotations

from homeassistant.helpers.device_registry import DeviceInfo

from .const import DOMAIN, DOCS_DEVICES


def signal_device_info(subentry_id: str, title: str, model: str, doc: str) -> DeviceInfo:
    """Attach a device to the docs page for that signal."""

    return DeviceInfo(
        identifiers={(DOMAIN, subentry_id)},
        name=title,
        manufacturer="HA Utils",
        model=model,
        configuration_url=f"{DOCS_DEVICES}/{doc}.md",
    )
