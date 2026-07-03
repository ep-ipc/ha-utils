"""Config flow for Home Assistant Utils."""

from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.core import callback
from homeassistant.helpers import issue_registry as ir

from .const import DOMAIN, ISSUE_PACKAGES_NOT_ENABLED, NAME
from .deploy import deploy_bundled_assets
from .prerequisites import check_prerequisites
from .repairs import async_update_repairs


class HaUtilsConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Home Assistant Utils."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.FlowResult:
        """Single-step setup: deploy bundle and create entry."""
        errors: dict[str, str] = {}

        if self._async_current_entries():
            return self.async_abort(reason="single_instance_allowed")

        if user_input is not None:
            deploy_result = await self.hass.async_add_executor_job(
                deploy_bundled_assets, self.hass
            )
            if deploy_result.errors:
                errors["base"] = "deploy_failed"

            if not errors:
                await async_update_repairs(
                    self.hass, deploy_result=deploy_result
                )
                status = check_prerequisites(self.hass)
                if not status.packages_enabled:
                    ir.async_create_issue(
                        self.hass,
                        DOMAIN,
                        ISSUE_PACKAGES_NOT_ENABLED,
                        is_fixable=False,
                        severity=ir.IssueSeverity.ERROR,
                        translation_key=ISSUE_PACKAGES_NOT_ENABLED,
                    )

                return self.async_create_entry(
                    title=NAME,
                    data={},
                )

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema({}),
            errors=errors,
            description_placeholders={
                "packages_snippet": (
                    "homeassistant:\n  packages: !include_dir_named packages"
                ),
            },
        )

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ) -> config_entries.OptionsFlow:
        """Return options flow (re-deploy bundled assets)."""
        return HaUtilsOptionsFlowHandler(config_entry)


class HaUtilsOptionsFlowHandler(config_entries.OptionsFlow):
    """Re-deploy missing bundled files."""

    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        self.config_entry = config_entry

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.FlowResult:
        """Offer re-deploy of missing bundle files."""
        if user_input is not None:
            deploy_result = await self.hass.async_add_executor_job(
                deploy_bundled_assets, self.hass
            )
            await async_update_repairs(
                self.hass, deploy_result=deploy_result
            )
            return self.async_create_entry(title="", data={})

        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema({}),
            description_placeholders={
                "action": "deploy missing package and blueprint files",
            },
        )
