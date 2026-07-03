"""Voice assistant exposure helpers."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant

_LOGGER = logging.getLogger(__name__)

DEFAULT_ASSISTANTS = ("conversation",)
KNOWN_ASSISTANTS = (
    "conversation",
    "cloud.alexa",
    "cloud.google_assistant",
)


@dataclass
class VoiceExposeResult:
    """Outcome of exposing entities to voice assistants."""

    exposed: list[str] = field(default_factory=list)
    skipped_already_exposed: list[str] = field(default_factory=list)
    skipped_missing: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)


def _unique(values: list[str] | tuple[str, ...]) -> list[str]:
    return list(dict.fromkeys(values))


def _target_entity_ids(
    hass: HomeAssistant,
    entity_ids: list[str] | None,
) -> list[str]:
    if entity_ids:
        return _unique(entity_ids)
    return sorted(hass.states.async_entity_ids())


def expose_entities_to_voice_assistants(
    hass: HomeAssistant,
    *,
    entity_ids: list[str] | None = None,
    assistants: list[str] | None = None,
) -> VoiceExposeResult:
    """Expose selected entities, or all unexposed entities when none are selected."""
    from homeassistant.components.homeassistant.exposed_entities import (
        async_expose_entity,
        async_should_expose,
    )

    target_assistants = _unique(assistants or list(DEFAULT_ASSISTANTS))
    result = VoiceExposeResult()

    for assistant in target_assistants:
        if assistant not in KNOWN_ASSISTANTS:
            result.errors.append(f"Unknown voice assistant: {assistant}")

    if result.errors:
        return result

    for entity_id in _target_entity_ids(hass, entity_ids):
        if hass.states.get(entity_id) is None:
            result.skipped_missing.append(entity_id)
            continue

        changed = False
        already_exposed_to_all = True
        for assistant in target_assistants:
            if async_should_expose(hass, assistant, entity_id):
                continue

            already_exposed_to_all = False
            async_expose_entity(hass, assistant, entity_id, True)
            changed = True

        if changed:
            result.exposed.append(entity_id)
        elif already_exposed_to_all:
            result.skipped_already_exposed.append(entity_id)

    _LOGGER.info(
        "Voice exposure complete: exposed=%d already_exposed=%d missing=%d",
        len(result.exposed),
        len(result.skipped_already_exposed),
        len(result.skipped_missing),
    )
    return result
