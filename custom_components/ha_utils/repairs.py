"""Repair issues for missing prerequisites."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from homeassistant.helpers import issue_registry as ir

from .const import (
    DOMAIN,
    ISSUE_PACKAGE_FILE_MISSING,
    ISSUE_PACKAGES_NOT_ENABLED,
    ISSUE_RESTART_REQUIRED,
)
from .deploy import DeployResult
from .prerequisites import PrerequisiteStatus, check_prerequisites

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant

_LOGGER = logging.getLogger(__name__)


async def async_update_repairs(
    hass: HomeAssistant,
    *,
    deploy_result: DeployResult | None = None,
) -> None:
    """Create or clear repair issues based on current state."""
    status = await hass.async_add_executor_job(check_prerequisites, hass)
    await _sync_repairs(hass, status, deploy_result)


async def async_clear_repairs(hass: HomeAssistant) -> None:
    """Remove all HA Utils repair issues."""
    for issue_id in (
        ISSUE_PACKAGES_NOT_ENABLED,
        ISSUE_PACKAGE_FILE_MISSING,
        ISSUE_RESTART_REQUIRED,
    ):
        ir.async_delete_issue(hass, DOMAIN, issue_id)


async def _sync_repairs(
    hass: HomeAssistant,
    status: PrerequisiteStatus,
    deploy_result: DeployResult | None,
) -> None:
    if not status.configuration_readable:
        _LOGGER.warning(
            "Could not read configuration.yaml; skipping packages repair check"
        )
    elif not status.packages_enabled:
        ir.async_create_issue(
            hass,
            DOMAIN,
            ISSUE_PACKAGES_NOT_ENABLED,
            is_fixable=False,
            severity=ir.IssueSeverity.ERROR,
            translation_key=ISSUE_PACKAGES_NOT_ENABLED,
        )
    else:
        ir.async_delete_issue(hass, DOMAIN, ISSUE_PACKAGES_NOT_ENABLED)

    if status.packages_enabled and not status.package_file_present:
        ir.async_create_issue(
            hass,
            DOMAIN,
            ISSUE_PACKAGE_FILE_MISSING,
            is_fixable=False,
            severity=ir.IssueSeverity.WARNING,
            translation_key=ISSUE_PACKAGE_FILE_MISSING,
        )
    else:
        ir.async_delete_issue(hass, DOMAIN, ISSUE_PACKAGE_FILE_MISSING)

    if deploy_result and deploy_result.package_copied:
        ir.async_create_issue(
            hass,
            DOMAIN,
            ISSUE_RESTART_REQUIRED,
            is_fixable=False,
            severity=ir.IssueSeverity.WARNING,
            translation_key=ISSUE_RESTART_REQUIRED,
        )
    else:
        ir.async_delete_issue(hass, DOMAIN, ISSUE_RESTART_REQUIRED)
