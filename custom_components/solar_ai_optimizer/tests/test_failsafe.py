"""Fail-safe watchdog and repair tests."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock

import pytest
from homeassistant.const import STATE_OFF, STATE_ON
from homeassistant.core import HomeAssistant, ServiceCall, State, SupportsResponse
from homeassistant.helpers import issue_registry as ir
from pytest_homeassistant_custom_component.common import (
    MockConfigEntry,
    mock_restore_cache,
)

from custom_components.solar_ai_optimizer.const import (
    CONF_GRID_CHARGE_ENABLE,
    CONF_MAX_GRID_CHARGE_CURRENT,
    DOMAIN,
)
from custom_components.solar_ai_optimizer.event import (
    EVENT_FAILSAFE_ACTIVATED,
    EVENT_FAILSAFE_CLEARED,
)
from custom_components.solar_ai_optimizer.failsafe import SolarFailsafeWatchdog
from custom_components.solar_ai_optimizer.helpers import parse_pulse
from custom_components.solar_ai_optimizer.repairs import (
    ISSUE_FAILSAFE_AMPS_FALLBACK,
    ISSUE_FAILSAFE_CLEARED_VERIFY,
    ISSUE_FAILSAFE_INCOMPLETE,
    FailsafeAmpsFallbackRepairFlow,
    FailsafeClearedVerifyRepairFlow,
    FailsafeIncompleteRepairFlow,
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


def test_parse_pulse_naive_as_utc() -> None:
    """Naive datetimes are interpreted as UTC, not local time."""
    naive = datetime(2026, 7, 8, 12, 0, 0)
    result = parse_pulse(naive)
    assert result is not None
    assert result == datetime(2026, 7, 8, 12, 0, 0, tzinfo=timezone.utc)

    result_str = parse_pulse("2026-07-08T12:00:00")
    assert result_str is not None
    assert result_str == datetime(2026, 7, 8, 12, 0, 0, tzinfo=timezone.utc)


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


async def test_create_fix_flow_dispatches(hass: HomeAssistant) -> None:
    """Repair flow factory dispatches to the correct custom flow class."""
    from homeassistant.components.repairs import ConfirmRepairFlow

    flow_incomplete = await async_create_fix_flow(
        hass, f"{ISSUE_FAILSAFE_INCOMPLETE}_some_entry"
    )
    assert isinstance(flow_incomplete, FailsafeIncompleteRepairFlow)

    flow_cleared = await async_create_fix_flow(
        hass, f"{ISSUE_FAILSAFE_CLEARED_VERIFY}_some_entry"
    )
    assert isinstance(flow_cleared, FailsafeClearedVerifyRepairFlow)

    flow_amps = await async_create_fix_flow(
        hass, f"{ISSUE_FAILSAFE_AMPS_FALLBACK}_some_entry"
    )
    assert isinstance(flow_amps, FailsafeAmpsFallbackRepairFlow)

    flow_unknown = await async_create_fix_flow(hass, "unknown_issue_id")
    assert isinstance(flow_unknown, ConfirmRepairFlow)


async def test_repair_flow_confirm_steps(hass: HomeAssistant) -> None:
    """Each custom repair flow shows a confirm form then finishes."""
    from homeassistant.data_entry_flow import FlowResultType

    for FlowClass in (
        FailsafeIncompleteRepairFlow,
        FailsafeClearedVerifyRepairFlow,
        FailsafeAmpsFallbackRepairFlow,
    ):
        flow = FlowClass()
        # async_step_init delegates to async_step_confirm
        result = await flow.async_step_init(None)
        assert result["type"] == FlowResultType.FORM
        assert result["step_id"] == "confirm"

        # Confirm with user input finishes the flow
        result2 = await flow.async_step_confirm({})
        assert result2["type"] == FlowResultType.CREATE_ENTRY


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

    failsafe_state = hass.states.get(
        "binary_sensor.solar_ai_optimizer_fail_safe_active"
    )
    assert failsafe_state is not None
    assert failsafe_state.state == STATE_ON

    event_state = hass.states.get("event.solar_ai_optimizer_integration_activity")
    assert event_state is not None
    assert event_state.attributes.get("event_type") == EVENT_FAILSAFE_ACTIVATED
    assert event_state.attributes.get("max_amps") == 55

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
    await hass.async_block_till_done()
    failsafe_state = hass.states.get(
        "binary_sensor.solar_ai_optimizer_fail_safe_active"
    )
    assert failsafe_state is not None
    assert failsafe_state.state == STATE_OFF
    event_state = hass.states.get("event.solar_ai_optimizer_integration_activity")
    assert event_state is not None
    assert event_state.attributes.get("event_type") == EVENT_FAILSAFE_CLEARED


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


async def test_failsafe_healthy_when_heartbeat_not_configured(
    hass: HomeAssistant, mock_client: AsyncMock, mock_config_entry: MockConfigEntry
) -> None:
    """heartbeat_configured=False means no signal; watchdog treats system as healthy."""
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

    watchdog = mock_config_entry.runtime_data.failsafe
    assert isinstance(watchdog, SolarFailsafeWatchdog)

    data = mock_config_entry.runtime_data
    # heartbeat_configured explicitly False → healthy regardless of pulse age.
    data.coordinator.data = {
        **(data.coordinator.data or {}),
        "heartbeat_configured": False,
        "heartbeat_last_pulse": None,
    }
    assert watchdog._is_healthy() is True

    # heartbeat_configured True with no pulse → unhealthy.
    data.coordinator.data = {
        **data.coordinator.data,
        "heartbeat_configured": True,
        "heartbeat_last_pulse": None,
    }
    assert watchdog._is_healthy() is False

    # heartbeat_configured None (not set) with no pulse → unhealthy.
    data.coordinator.data = {
        **data.coordinator.data,
        "heartbeat_configured": None,
        "heartbeat_last_pulse": None,
    }
    assert watchdog._is_healthy() is False


async def test_failsafe_stop_cancels_apply_task(
    hass: HomeAssistant, mock_client: AsyncMock, mock_config_entry: MockConfigEntry
) -> None:
    """async_stop cancels _apply_task without waiting for service calls."""
    import asyncio

    mock_config_entry.add_to_hass(hass)

    async def _never_completes() -> None:
        await asyncio.sleep(3600)

    # Inject a never-completing task directly into a minimal watchdog.
    from custom_components.solar_ai_optimizer.coordinator import SolarAiCoordinator

    coordinator = SolarAiCoordinator(
        hass, config_entry=mock_config_entry, client=mock_client
    )
    watchdog = SolarFailsafeWatchdog(hass, mock_config_entry, coordinator, AsyncMock())
    task: asyncio.Task[None] = hass.async_create_task(_never_completes())
    watchdog._apply_task = task

    assert not task.done()
    watchdog.async_stop()
    assert watchdog._apply_task is None

    # One event-loop turn lets the task process the cancellation.
    await asyncio.sleep(0)
    assert task.cancelled()


async def test_failsafe_cleared_creates_verify_issue(
    hass: HomeAssistant, mock_client: AsyncMock, mock_config_entry: MockConfigEntry
) -> None:
    """Clearing the latch creates a failsafe_cleared_verify repair issue."""
    calls: list[ServiceCall] = []

    async def _capture(call: ServiceCall) -> None:
        calls.append(call)

    _register = getattr(hass.services, "async_register")
    _register("switch", "turn_on", _capture, supports_response=SupportsResponse.NONE)
    _register("number", "set_value", _capture, supports_response=SupportsResponse.NONE)

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

    # Latch the watchdog.
    stale_pulse = (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat()
    data.coordinator.data = {
        **(data.coordinator.data or {}),
        "heartbeat_last_pulse": stale_pulse,
        "config": {"grid_charge": {"max_grid_charge_a": 50}},
    }
    watchdog._unhealthy_since = datetime.now(timezone.utc) - timedelta(seconds=5)
    watchdog._latched = False
    watchdog._evaluate()
    await hass.async_block_till_done()
    assert watchdog._latched is True

    # Now recover.
    fresh = datetime.now(timezone.utc).isoformat()
    data.coordinator.data = {**data.coordinator.data, "heartbeat_last_pulse": fresh}
    watchdog._evaluate()
    assert watchdog._latched is False

    issues = ir.async_get(hass)
    issue_id = f"{ISSUE_FAILSAFE_CLEARED_VERIFY}_{mock_config_entry.entry_id}"
    assert issues.async_get_issue(DOMAIN, issue_id) is not None


async def test_failsafe_clear_mid_apply_skips_activation(
    hass: HomeAssistant, mock_client: AsyncMock, mock_config_entry: MockConfigEntry
) -> None:
    """A clear that lands between the two apply awaits skips activation."""
    calls: list[ServiceCall] = []

    async def _turn_on(call: ServiceCall) -> None:
        calls.append(call)
        # Simulate a concurrent recovery: heartbeat becomes healthy and
        # evaluate() clears the latch while the switch call is in flight.
        watchdog._latched = False

    async def _set_value(call: ServiceCall) -> None:
        calls.append(call)

    _register = getattr(hass.services, "async_register")
    _register("switch", "turn_on", _turn_on, supports_response=SupportsResponse.NONE)
    _register(
        "number", "set_value", _set_value, supports_response=SupportsResponse.NONE
    )

    # Fresh pulse at setup so async_start's initial evaluate stays healthy;
    # the test drives the unhealthy transition explicitly below.
    mock_client.get_health = AsyncMock(
        return_value={
            "install_id": "install-abc12345",
            "version": "0.6.11-beta.2",
            "heartbeat_last_pulse": datetime.now(timezone.utc).isoformat(),
            "heartbeat_configured": True,
        }
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
    assert watchdog._latched is False

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

    # switch.turn_on fired and cleared the latch mid-apply: number.set_value
    # must never run and the activation event must never fire.
    assert len(calls) == 1
    event_state = hass.states.get("event.solar_ai_optimizer_integration_activity")
    assert event_state is not None
    assert event_state.attributes.get("event_type") != EVENT_FAILSAFE_ACTIVATED


async def test_failsafe_evaluate_cancels_running_apply_task(
    hass: HomeAssistant, mock_client: AsyncMock, mock_config_entry: MockConfigEntry
) -> None:
    """Clearing the latch via _evaluate cancels an in-flight apply task."""
    import asyncio

    calls: list[ServiceCall] = []
    block_event = asyncio.Event()

    async def _turn_on_blocking(call: ServiceCall) -> None:
        calls.append(call)
        await block_event.wait()

    async def _set_value(call: ServiceCall) -> None:
        calls.append(call)

    _register = getattr(hass.services, "async_register")
    _register(
        "switch",
        "turn_on",
        _turn_on_blocking,
        supports_response=SupportsResponse.NONE,
    )
    _register(
        "number", "set_value", _set_value, supports_response=SupportsResponse.NONE
    )

    mock_client.get_health = AsyncMock(
        return_value={
            "install_id": "install-abc12345",
            "version": "0.6.11-beta.2",
            "heartbeat_last_pulse": datetime.now(timezone.utc).isoformat(),
            "heartbeat_configured": True,
        }
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
    assert watchdog._latched is False

    stale_pulse = (datetime.now(timezone.utc) - timedelta(seconds=120)).isoformat()
    data.coordinator.data = {
        **(data.coordinator.data or {}),
        "heartbeat_last_pulse": stale_pulse,
        "config": {"grid_charge": {"max_grid_charge_a": 55}},
    }
    watchdog._unhealthy_since = datetime.now(timezone.utc) - timedelta(seconds=5)
    watchdog._evaluate()
    # Let the apply task start and block on the switch.turn_on call.
    await asyncio.sleep(0)
    await asyncio.sleep(0)
    assert len(calls) == 1
    task = watchdog._apply_task
    assert task is not None
    assert not task.done()

    # Heartbeat recovers: evaluate() should cancel the in-flight apply task.
    fresh_pulse = datetime.now(timezone.utc).isoformat()
    data.coordinator.data = {**data.coordinator.data, "heartbeat_last_pulse": fresh_pulse}
    watchdog._evaluate()
    assert watchdog._apply_task is None
    await hass.async_block_till_done()
    assert task.cancelled()

    # The blocked switch call never returned; number.set_value never ran and
    # no activation event was recorded.
    assert len(calls) == 1
    event_state = hass.states.get("event.solar_ai_optimizer_integration_activity")
    assert event_state is not None
    assert event_state.attributes.get("event_type") != EVENT_FAILSAFE_ACTIVATED


async def test_failsafe_number_call_failure_skips_activation(
    hass: HomeAssistant, mock_client: AsyncMock, mock_config_entry: MockConfigEntry
) -> None:
    """A failure on the second (number.set_value) call skips activation."""

    async def _turn_on(_call: ServiceCall) -> None:
        return None

    async def _boom(_call: ServiceCall) -> None:
        raise RuntimeError("nope")

    _register = getattr(hass.services, "async_register")
    _register("switch", "turn_on", _turn_on, supports_response=SupportsResponse.NONE)
    _register("number", "set_value", _boom, supports_response=SupportsResponse.NONE)

    mock_client.get_health = AsyncMock(
        return_value={
            "install_id": "install-abc12345",
            "version": "0.6.11-beta.2",
            "heartbeat_last_pulse": datetime.now(timezone.utc).isoformat(),
            "heartbeat_configured": True,
        }
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
    watchdog._evaluate()
    await hass.async_block_till_done()

    event_state = hass.states.get("event.solar_ai_optimizer_integration_activity")
    assert event_state is not None
    assert event_state.attributes.get("event_type") != EVENT_FAILSAFE_ACTIVATED


async def test_failsafe_clear_after_number_call_skips_activation(
    hass: HomeAssistant, mock_client: AsyncMock, mock_config_entry: MockConfigEntry
) -> None:
    """A clear that lands right after the number.set_value call skips activation."""
    calls: list[ServiceCall] = []

    async def _turn_on(call: ServiceCall) -> None:
        calls.append(call)

    async def _set_value(call: ServiceCall) -> None:
        calls.append(call)
        # Simulate a concurrent recovery landing after this call completes
        # but before the apply coroutine checks the latch again.
        watchdog._latched = False

    _register = getattr(hass.services, "async_register")
    _register("switch", "turn_on", _turn_on, supports_response=SupportsResponse.NONE)
    _register(
        "number", "set_value", _set_value, supports_response=SupportsResponse.NONE
    )

    mock_client.get_health = AsyncMock(
        return_value={
            "install_id": "install-abc12345",
            "version": "0.6.11-beta.2",
            "heartbeat_last_pulse": datetime.now(timezone.utc).isoformat(),
            "heartbeat_configured": True,
        }
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
    watchdog._evaluate()
    await hass.async_block_till_done()

    assert len(calls) == 2
    event_state = hass.states.get("event.solar_ai_optimizer_integration_activity")
    assert event_state is not None
    assert event_state.attributes.get("event_type") != EVENT_FAILSAFE_ACTIVATED


async def test_failsafe_restore_latched_and_healthy_clears(
    hass: HomeAssistant, mock_client: AsyncMock, mock_config_entry: MockConfigEntry
) -> None:
    """A restored ON latch is adopted, then cleared when startup is healthy."""
    mock_restore_cache(
        hass,
        [State("binary_sensor.solar_ai_optimizer_fail_safe_active", STATE_ON)],
    )

    fresh_pulse = datetime.now(timezone.utc).isoformat()
    mock_client.get_health = AsyncMock(
        return_value={
            "install_id": "install-abc12345",
            "version": "0.6.11-beta.2",
            "heartbeat_last_pulse": fresh_pulse,
            "heartbeat_configured": True,
        }
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

    watchdog = mock_config_entry.runtime_data.failsafe
    assert isinstance(watchdog, SolarFailsafeWatchdog)
    # The restored ON state was adopted, then cleared because the heartbeat
    # is healthy at startup.
    assert watchdog._latched is False

    failsafe_state = hass.states.get(
        "binary_sensor.solar_ai_optimizer_fail_safe_active"
    )
    assert failsafe_state is not None
    assert failsafe_state.state == STATE_OFF
