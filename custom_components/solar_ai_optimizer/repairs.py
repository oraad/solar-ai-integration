"""Repair flows for Solar AI Optimizer."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from homeassistant.components.repairs import ConfirmRepairFlow, RepairsFlow
from homeassistant.core import HomeAssistant
from homeassistant.helpers import issue_registry as ir

from .const import (
    CONF_GRID_CHARGE_ENABLE,
    CONF_MAX_GRID_CHARGE_CURRENT,
    DOMAIN,
)

ISSUE_FAILSAFE_INCOMPLETE = "failsafe_incomplete"


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


async def async_create_fix_flow(
    hass: HomeAssistant,
    issue_id: str,
) -> RepairsFlow:
    """Create a repair flow for the given issue id."""
    _ = hass
    _ = issue_id
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
