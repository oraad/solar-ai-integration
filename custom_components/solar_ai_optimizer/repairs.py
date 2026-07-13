"""Repair flows for Solar AI Optimizer."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

import voluptuous as vol

from homeassistant.components.repairs import ConfirmRepairFlow, RepairsFlow
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers import issue_registry as ir

from .const import (
    CONF_GRID_CHARGE_ENABLE,
    CONF_MAX_GRID_CHARGE_CURRENT,
    DOMAIN,
)

ISSUE_FAILSAFE_INCOMPLETE = "failsafe_incomplete"
ISSUE_FAILSAFE_CLEARED_VERIFY = "failsafe_cleared_verify"
ISSUE_FAILSAFE_AMPS_FALLBACK = "failsafe_amps_fallback"


def async_check_failsafe_repair(
    hass: HomeAssistant,
    entry_id: str,
    *,
    switch_id: str | None,
    number_id: str | None,
) -> None:
    """Create or clear the incomplete fail-safe repair issue."""
    issue_id = f"{ISSUE_FAILSAFE_INCOMPLETE}_{entry_id}"
    incomplete = bool(switch_id) ^ bool(number_id)
    if incomplete:
        ir.async_create_issue(
            hass,
            DOMAIN,
            issue_id,
            is_fixable=True,
            severity=ir.IssueSeverity.WARNING,
            translation_key=ISSUE_FAILSAFE_INCOMPLETE,
            data={"entry_id": entry_id},
        )
    else:
        ir.async_delete_issue(hass, DOMAIN, issue_id)


def async_create_failsafe_cleared_issue(hass: HomeAssistant, entry_id: str) -> None:
    """Create a repair issue after the fail-safe latch clears.

    Persists until the user dismisses it via ConfirmRepairFlow, reminding them
    to verify inverter settings before Solar reclaims control.
    """
    ir.async_create_issue(
        hass,
        DOMAIN,
        f"{ISSUE_FAILSAFE_CLEARED_VERIFY}_{entry_id}",
        is_fixable=True,
        severity=ir.IssueSeverity.WARNING,
        translation_key=ISSUE_FAILSAFE_CLEARED_VERIFY,
        data={"entry_id": entry_id},
    )


def async_create_amps_fallback_issue(hass: HomeAssistant, entry_id: str) -> None:
    """Create a repair issue when max_amps falls back to the built-in default.

    Indicates that Solar config was unavailable when the fail-safe fired.
    """
    ir.async_create_issue(
        hass,
        DOMAIN,
        f"{ISSUE_FAILSAFE_AMPS_FALLBACK}_{entry_id}",
        is_fixable=True,
        severity=ir.IssueSeverity.WARNING,
        translation_key=ISSUE_FAILSAFE_AMPS_FALLBACK,
        data={"entry_id": entry_id},
    )


def async_clear_amps_fallback_issue(hass: HomeAssistant, entry_id: str) -> None:
    """Delete the amps-fallback repair issue (e.g. after fail-safe clears)."""
    ir.async_delete_issue(hass, DOMAIN, f"{ISSUE_FAILSAFE_AMPS_FALLBACK}_{entry_id}")


class FailsafeIncompleteRepairFlow(RepairsFlow):
    """Guide the user to set both fail-safe entities via Configure."""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        return await self.async_step_confirm(user_input)

    async def async_step_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        if user_input is not None:
            return self.async_create_entry(data={})
        return self.async_show_form(step_id="confirm", data_schema=vol.Schema({}))


class FailsafeClearedVerifyRepairFlow(RepairsFlow):
    """Ask the user to verify inverter settings after fail-safe cleared."""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        return await self.async_step_confirm(user_input)

    async def async_step_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        if user_input is not None:
            return self.async_create_entry(data={})
        return self.async_show_form(step_id="confirm", data_schema=vol.Schema({}))


class FailsafeAmpsFallbackRepairFlow(RepairsFlow):
    """Ask the user to verify Solar config after amps fallback to default."""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        return await self.async_step_confirm(user_input)

    async def async_step_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        if user_input is not None:
            return self.async_create_entry(data={})
        return self.async_show_form(step_id="confirm", data_schema=vol.Schema({}))


async def async_create_fix_flow(
    hass: HomeAssistant,
    issue_id: str,
) -> RepairsFlow:
    """Create a repair flow for the given issue id."""
    _ = hass
    if issue_id.startswith(ISSUE_FAILSAFE_INCOMPLETE):
        return FailsafeIncompleteRepairFlow()
    if issue_id.startswith(ISSUE_FAILSAFE_CLEARED_VERIFY):
        return FailsafeClearedVerifyRepairFlow()
    if issue_id.startswith(ISSUE_FAILSAFE_AMPS_FALLBACK):
        return FailsafeAmpsFallbackRepairFlow()
    return ConfirmRepairFlow()


def failsafe_entity_ids(
    entry_options: Mapping[str, Any], entry_data: Mapping[str, Any]
) -> tuple[str | None, str | None]:
    """Return configured fail-safe entity ids from options or data."""
    switch_id = entry_options.get(CONF_GRID_CHARGE_ENABLE) or entry_data.get(
        CONF_GRID_CHARGE_ENABLE
    )
    number_id = entry_options.get(CONF_MAX_GRID_CHARGE_CURRENT) or entry_data.get(
        CONF_MAX_GRID_CHARGE_CURRENT
    )
    return (
        str(switch_id) if switch_id else None,
        str(number_id) if number_id else None,
    )
