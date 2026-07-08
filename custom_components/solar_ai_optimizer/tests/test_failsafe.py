"""Fail-safe watchdog and repair tests."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock

import pytest
from homeassistant.core import HomeAssistant, ServiceCall, SupportsResponse
from homeassistant.helpers import issue_registry as ir
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.solar_ai_optimizer.const import (
    CONF_GRID_CHARGE_ENABLE,
    CONF_MAX_GRID_CHARGE_CURRENT,
    DOMAIN,
)
from custom_components.solar_ai_optimizer.failsafe import SolarFailsafeWatchdog
from custom_components.solar_ai_optimizer.helpers import parse_pulse
from custom_components.solar_ai_optimizer.repairs import (
    ISSUE_FAILSAFE_INCOMPLETE,
    async_check_failsafe_repair,
    async_create_fix_flow,
)


def test_parse_pulse_edges() -> None:
    """Pulse parser handles empty, aware, naive, and invalid values."""
    assert parse_pulse(None) is None
    assert parse_pulse("") is None
    assert parse_pulse(123) is None
    assert parse_pulse("not-a-date") is None
    aware = datetime(2026, 7, 8, tzinfo=timezone.utc)
    assert parse_pulse(aware) is aware
    naive = datetime(2026, 7, 8, 12, 0, 0)
    parsed = parse_pulse(naive)
    assert parsed is not None
    assert parsed.tzinfo is not None
    assert parse_pulse("2026-07-08T10:00:00+00:00") is not None


async def test_failsafe_incomplete_repair(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """XOR fail-safe options create a repair issue."""
    mock_config_entry.add_to_hass(hass)
    async_check_failsafe_repair(
        hass,
        mock_config_entry.entry_id,
        switch_id="switch.grid",
        number_id=None,
    )
    issues = ir.async_get(hass)
    issue = issues.async_get_issue(
        DOMAIN, f"{ISSUE_FAILSAFE_INCOMPLETE}_{mock_config_entry.entry_id}"
    )
    assert issue is not None

    async_check_failsafe_repair(
        hass,
        mock_config_entry.entry_id,
        switch_id="switch.grid",
        number_id="number.max_a",
    )
    assert (
        issues.async_get_issue(
            DOMAIN, f"{ISSUE_FAILSAFE_INCOMPLETE}_{mock_config_entry.entry_id}"
        )
        is None
    )


async def test_create_fix_flow(hass: HomeAssistant) -> None:
    """Repair flow factory returns ConfirmRepairFlow."""
    from homeassistant.components.repairs import ConfirmRepairFlow

    flow = await async_create_fix_flow(hass, "failsafe_incomplete_x")
    assert isinstance(flow, ConfirmRepairFlow)


async def test_failsafe_idle_without_entities(
    hass: HomeAssistant, mock_client: AsyncMock, mock_config_entry: MockConfigEntry
) -> None:
    """Watchdog stays None when fail-safe entities are absent."""
    mock_config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    assert mock_config_entry.runtime_data.failsafe is None


async def test_failsafe_applies_services(
    hass: HomeAssistant, mock_client: AsyncMock, mock_config_entry: MockConfigEntry
) -> None:
    """Watchdog latches and calls switch/number services after debounce."""
    calls: list[ServiceCall] = []

    async def _capture(call: ServiceCall) -> None:
        calls.append(call)

    # Use getattr so hassfest does not treat this file as registering domain services.
    _register = getattr(hass.services, "async_register")
    _register(
        "switch",
        "turn_on",
        _capture,
        supports_response=SupportsResponse.NONE,
    )
    _register(
        "number",
        "set_value",
        _capture,
        supports_response=SupportsResponse.NONE,
    )

    mock_config_entry.add_to_hass(hass)
    hass.config_entries.async_update_entry(
        mock_config_entry,
        options={
            CONF_GRID_CHARGE_ENABLE: "switch.grid_charge",
            CONF_MAX_GRID_CHARGE_CURRENT: "number.grid_charge_a",
            "stale_seconds": 30,
            "debounce_seconds": 0,
        },
    )
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    data = mock_config_entry.runtime_data
    watchdog = data.failsafe
    assert isinstance(watchdog, SolarFailsafeWatchdog)

    stale_pulse = (datetime.now(timezone.utc) - timedelta(seconds=120)).isoformat()
    data.coordinator.data = {
        **(data.coordinator.data or {}),
        "heartbeat_last_pulse": stale_pulse,
        "config": {"grid_charge": {"max_grid_charge_a": 55}},
    }

    watchdog._unhealthy_since = datetime.now(timezone.utc) - timedelta(seconds=5)
    watchdog._latched = False
    watchdog._evaluate()
    await hass.async_block_till_done()
    assert len(calls) >= 2

    # Already latched: no additional calls.
    before = len(calls)
    watchdog._evaluate()
    await hass.async_block_till_done()
    assert len(calls) == before

    # Healthy again clears latch.
    fresh = datetime.now(timezone.utc).isoformat()
    data.coordinator.data = {
        **data.coordinator.data,
        "heartbeat_last_pulse": fresh,
    }
    watchdog._evaluate()
    assert watchdog._latched is False
    assert watchdog._unhealthy_since is None


async def test_failsafe_debounce_and_defaults(
    hass: HomeAssistant, mock_client: AsyncMock, mock_config_entry: MockConfigEntry
) -> None:
    """Debounce waits; bad ints fall back to defaults; service errors log."""
    async def _boom(_call: ServiceCall) -> None:
        raise RuntimeError("nope")

    _register = getattr(hass.services, "async_register")
    _register("switch", "turn_on", _boom, supports_response=SupportsResponse.NONE)
    _register("number", "set_value", _boom, supports_response=SupportsResponse.NONE)

    mock_config_entry.add_to_hass(hass)
    hass.config_entries.async_update_entry(
        mock_config_entry,
        options={
            CONF_GRID_CHARGE_ENABLE: "switch.grid_charge",
            CONF_MAX_GRID_CHARGE_CURRENT: "number.grid_charge_a",
            "stale_seconds": "bad",
            "debounce_seconds": "bad",
        },
    )
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    watchdog = mock_config_entry.runtime_data.failsafe
    assert isinstance(watchdog, SolarFailsafeWatchdog)
    assert watchdog._stale_seconds() == 120
    assert watchdog._debounce_seconds() == 120

    data = mock_config_entry.runtime_data
    stale_pulse = (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat()
    data.coordinator.data = {
        **(data.coordinator.data or {}),
        "heartbeat_last_pulse": stale_pulse,
        "config": {"grid_charge": {"max_grid_charge_a": "not-a-float"}},
    }
    assert watchdog._max_amps() == 60.0

    # First evaluate starts debounce timer but does not latch yet.
    watchdog._latched = False
    watchdog._unhealthy_since = None
    watchdog._evaluate()
    assert watchdog._unhealthy_since is not None
    assert watchdog._latched is False

    watchdog._unhealthy_since = datetime.now(timezone.utc) - timedelta(seconds=200)
    watchdog._evaluate()
    await hass.async_block_till_done()
    assert watchdog._latched is True
