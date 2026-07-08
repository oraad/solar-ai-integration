"""Entity platform tests."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock

import pytest
from aiohttp import ClientError, ClientResponseError
from homeassistant.components.update import UpdateEntityFeature
from homeassistant.const import STATE_OFF, STATE_ON, EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry as er
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.solar_ai_optimizer.binary_sensor import (
    SolarAiHealthyBinarySensor,
)
from custom_components.solar_ai_optimizer.update import SolarAiUpdateEntity


async def test_entities_created(
    hass: HomeAssistant, mock_client: AsyncMock, mock_config_entry: MockConfigEntry
) -> None:
    """Setup creates sensor, binary_sensor, and update entities."""
    mock_config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert hass.states.get("sensor.solar_ai_optimizer_version") is not None
    assert hass.states.get("sensor.solar_ai_optimizer_last_pulse") is not None
    healthy = hass.states.get("binary_sensor.solar_ai_optimizer_healthy")
    assert healthy is not None
    assert healthy.state in (STATE_ON, STATE_OFF)

    registry = er.async_get(hass)
    entries = er.async_entries_for_config_entry(registry, mock_config_entry.entry_id)
    install_entries = [
        e for e in entries if e.unique_id.endswith("_install_visibility")
    ]
    assert install_entries
    assert install_entries[0].disabled_by is not None
    assert install_entries[0].entity_category == EntityCategory.DIAGNOSTIC


async def test_healthy_stale_and_bad_options(
    hass: HomeAssistant, mock_client: AsyncMock, mock_config_entry: MockConfigEntry
) -> None:
    """Healthy sensor reflects pulse age; bad stale options use default."""
    mock_config_entry.add_to_hass(hass)
    hass.config_entries.async_update_entry(
        mock_config_entry, options={"stale_seconds": "nope"}
    )
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    coordinator = mock_config_entry.runtime_data.coordinator
    entity = SolarAiHealthyBinarySensor(coordinator, mock_config_entry)
    entity.hass = hass

    coordinator.data = {
        **(coordinator.data or {}),
        "heartbeat_last_pulse": (
            datetime.now(timezone.utc) - timedelta(seconds=300)
        ).isoformat(),
    }
    assert entity.is_on is False
    assert entity._stale_seconds() == 120

    coordinator.data = {**(coordinator.data or {}), "heartbeat_last_pulse": None}
    assert entity.is_on is False

    coordinator.data = None  # type: ignore[assignment]
    assert entity.is_on is None


async def test_update_entity_install(
    hass: HomeAssistant, mock_client: AsyncMock, mock_config_entry: MockConfigEntry
) -> None:
    """Update entity exposes install and can trigger apply_update."""
    mock_config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    state = hass.states.get("update.solar_ai_optimizer_software")
    assert state is not None
    assert state.attributes.get("installed_version") == "0.6.11-beta.2"
    assert state.attributes.get("latest_version") == "0.6.12"

    await hass.services.async_call(
        "update",
        "install",
        {"entity_id": "update.solar_ai_optimizer_software"},
        blocking=True,
    )
    mock_client.apply_update.assert_awaited()


async def test_update_entity_addon_and_errors(
    hass: HomeAssistant, mock_client: AsyncMock, mock_config_entry: MockConfigEntry
) -> None:
    """Addon deployment disables INSTALL; apply errors raise HomeAssistantError."""
    mock_client.get_update_info = AsyncMock(
        return_value={
            "current_version": "0.6.11",
            "latest_version": "0.6.12",
            "can_apply": False,
            "deployment": "addon",
            "update_in_progress": False,
            "apply_instructions": "Use Supervisor",
            "release_notes": 123,
            "release_url": "https://example.com",
            "pull_percent": None,
        }
    )
    mock_config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    coordinator = mock_config_entry.runtime_data.coordinator
    entity = SolarAiUpdateEntity(coordinator)
    entity.hass = hass
    assert UpdateEntityFeature.INSTALL not in entity.supported_features
    assert entity.extra_state_attributes["deployment"] == "addon"
    assert entity.extra_state_attributes["apply_instructions"] == "Use Supervisor"
    assert await entity.async_release_notes() is None

    entity.coordinator.data = None  # type: ignore[assignment]
    assert entity.installed_version is None
    assert entity.latest_version is None
    assert entity.release_url is None
    assert entity.in_progress is None
    assert entity.update_percentage is None
    assert await entity.async_release_notes() is None

    coordinator.data = {
        "can_apply": True,
        "deployment": "docker",
        "current_version": "1",
        "latest_version": "2",
        "update_in_progress": False,
        "health": {},
        "update": {},
        "config": None,
        "update_available": True,
    }
    entity = SolarAiUpdateEntity(coordinator)
    entity.hass = hass
    mock_client.apply_update = AsyncMock(
        side_effect=ClientResponseError(
            request_info=None,  # type: ignore[arg-type]
            history=(),
            status=503,
            message="x",
        )
    )
    with pytest.raises(HomeAssistantError):
        await entity.async_install(version=None, backup=False)

    mock_client.apply_update = AsyncMock(side_effect=ClientError("net"))
    with pytest.raises(HomeAssistantError):
        await entity.async_install(version="1.2.3", backup=False)
