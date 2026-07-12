"""Diagnostics for Solar AI Optimizer."""

from __future__ import annotations

from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.core import HomeAssistant

from . import SolarAiConfigEntry
from .const import (
    CONF_ACCESS_TOKEN,
    CONF_DEBOUNCE_SECONDS,
    CONF_GRID_CHARGE_ENABLE,
    CONF_MAX_GRID_CHARGE_CURRENT,
    CONF_STALE_SECONDS,
    DEFAULT_MAX_GRID_CHARGE_A,
)
from .helpers import max_grid_charge_amps

TO_REDACT = {CONF_ACCESS_TOKEN}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant,
    entry: SolarAiConfigEntry,
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    _ = hass
    data = entry.runtime_data
    coordinator = data.coordinator
    options = entry.options

    switch_id = options.get(CONF_GRID_CHARGE_ENABLE)
    number_id = options.get(CONF_MAX_GRID_CHARGE_CURRENT)
    failsafe_configured = bool(switch_id and number_id)
    failsafe_incomplete = bool(switch_id) ^ bool(number_id)
    resolved_max_amps = max_grid_charge_amps(coordinator.data)
    if resolved_max_amps is None:
        resolved_max_amps = DEFAULT_MAX_GRID_CHARGE_A

    return {
        "entry": {
            "title": entry.title,
            "unique_id": entry.unique_id,
            "data": async_redact_data(dict(entry.data), TO_REDACT),
            "options": dict(options),
        },
        "failsafe": {
            "watchdog_active": data.failsafe is not None,
            "configured": failsafe_configured,
            "incomplete": failsafe_incomplete,
            "stale_seconds": options.get(CONF_STALE_SECONDS),
            "debounce_seconds": options.get(CONF_DEBOUNCE_SECONDS),
            "max_grid_charge_amps": resolved_max_amps,
        },
        "coordinator": {
            "last_update_success": coordinator.last_update_success,
            "data": coordinator.data,
        },
    }
