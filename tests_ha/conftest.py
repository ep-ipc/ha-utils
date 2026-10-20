"""Fixtures for tests that load HA Utils in a real Home Assistant."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import patch

import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from homeassistant.config_entries import ConfigSubentryData
from homeassistant.core import HomeAssistant, ServiceResponse, SupportsResponse

# Import before the hass fixture puts its own custom_components on sys.path.
import custom_components.ha_utils  # noqa: F401

DOMAIN = "ha_utils"


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations):
    yield


@pytest.fixture(autouse=True)
def no_deploy():
    """Setup must not copy bundled files into the test config dir."""

    with patch(
        "custom_components.ha_utils.deploy_bundled_assets",
        return_value=SimpleNamespace(copied=[], skipped=[], errors=[]),
    ):
        yield


@pytest.fixture
def forecast(hass: HomeAssistant) -> dict[str, list[dict]]:
    """A stand-in weather.get_forecasts that returns whatever rows the test sets."""

    rows: dict[str, list[dict]] = {}

    async def _get_forecasts(call) -> ServiceResponse:
        entity_ids = call.data.get("entity_id") or []
        if isinstance(entity_ids, str):
            entity_ids = [entity_ids]
        return {entity_id: {"forecast": rows.get(entity_id, [])} for entity_id in entity_ids}

    hass.services.async_register(
        "weather", "get_forecasts", _get_forecasts, supports_response=SupportsResponse.ONLY
    )
    return rows


def subentry(kind: str, title: str, data: dict) -> ConfigSubentryData:
    return ConfigSubentryData(data=data, subentry_type=kind, title=title, unique_id=None)


async def setup_entry(hass: HomeAssistant, *subentries: ConfigSubentryData) -> MockConfigEntry:
    entry = MockConfigEntry(domain=DOMAIN, data={}, subentries_data=list(subentries))
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    return entry
