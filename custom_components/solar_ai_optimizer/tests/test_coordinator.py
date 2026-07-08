"""Coordinator unit tests."""

from __future__ import annotations

from datetime import timedelta
from unittest.mock import AsyncMock

import pytest
from aiohttp import ClientError, ClientResponseError
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import UpdateFailed
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.solar_ai_optimizer.const import UPDATE_POLL_INTERVAL
from custom_components.solar_ai_optimizer.coordinator import SolarAiCoordinator


def _http_error(status: int) -> ClientResponseError:
    err = ClientResponseError(
        request_info=None,  # type: ignore[arg-type]
        history=(),
        status=status,
        message="err",
    )
    # Avoid aiohttp __str__ accessing request_info.real_url in f-strings.
    err.__str__ = lambda: f"{status} err"  # type: ignore[method-assign]
    return err


async def test_coordinator_success(
    hass: HomeAssistant, mock_client: AsyncMock, mock_config_entry: MockConfigEntry
) -> None:
    """Coordinator aggregates health and update payloads."""
    mock_config_entry.add_to_hass(hass)
    coordinator = SolarAiCoordinator(
        hass, config_entry=mock_config_entry, client=mock_client
    )
    data = await coordinator._async_update_data()
    assert data["version"] == "0.6.11-beta.2"
    assert data["can_apply"] is True
    assert data["update_available"] is True


async def test_coordinator_auth_failed(
    hass: HomeAssistant, mock_client: AsyncMock, mock_config_entry: MockConfigEntry
) -> None:
    """401 from health becomes ConfigEntryAuthFailed."""
    mock_config_entry.add_to_hass(hass)
    mock_client.get_health = AsyncMock(side_effect=_http_error(401))
    coordinator = SolarAiCoordinator(
        hass, config_entry=mock_config_entry, client=mock_client
    )
    with pytest.raises(ConfigEntryAuthFailed):
        await coordinator._async_update_data()


async def test_coordinator_health_http_error(
    hass: HomeAssistant, mock_client: AsyncMock, mock_config_entry: MockConfigEntry
) -> None:
    """Non-401 health HTTP becomes UpdateFailed."""
    mock_config_entry.add_to_hass(hass)
    mock_client.get_health = AsyncMock(side_effect=_http_error(500))
    coordinator = SolarAiCoordinator(
        hass, config_entry=mock_config_entry, client=mock_client
    )
    with pytest.raises(UpdateFailed):
        await coordinator._async_update_data()


async def test_coordinator_update_failed(
    hass: HomeAssistant, mock_client: AsyncMock, mock_config_entry: MockConfigEntry
) -> None:
    """Network error becomes UpdateFailed."""
    mock_config_entry.add_to_hass(hass)
    mock_client.get_health = AsyncMock(side_effect=ClientError("boom"))
    coordinator = SolarAiCoordinator(
        hass, config_entry=mock_config_entry, client=mock_client
    )
    with pytest.raises(UpdateFailed):
        await coordinator._async_update_data()


async def test_coordinator_update_info_errors(
    hass: HomeAssistant, mock_client: AsyncMock, mock_config_entry: MockConfigEntry
) -> None:
    """Update endpoint auth and network failures."""
    mock_config_entry.add_to_hass(hass)
    coordinator = SolarAiCoordinator(
        hass, config_entry=mock_config_entry, client=mock_client
    )

    mock_client.get_update_info = AsyncMock(side_effect=_http_error(401))
    with pytest.raises(ConfigEntryAuthFailed):
        await coordinator._async_update_data()

    mock_client.get_update_info = AsyncMock(side_effect=_http_error(502))
    with pytest.raises(UpdateFailed):
        await coordinator._async_update_data()

    mock_client.get_update_info = AsyncMock(side_effect=ClientError("x"))
    with pytest.raises(UpdateFailed):
        await coordinator._async_update_data()


async def test_coordinator_config_best_effort(
    hass: HomeAssistant, mock_client: AsyncMock, mock_config_entry: MockConfigEntry
) -> None:
    """Config fetch failures are ignored."""
    mock_config_entry.add_to_hass(hass)
    mock_client.get_config = AsyncMock(side_effect=_http_error(403))
    coordinator = SolarAiCoordinator(
        hass, config_entry=mock_config_entry, client=mock_client
    )
    data = await coordinator._async_update_data()
    assert data["config"] is None

    mock_client.get_config = AsyncMock(side_effect=ClientError("x"))
    data = await coordinator._async_update_data()
    assert data["config"] is None


async def test_coordinator_faster_poll_during_update(
    hass: HomeAssistant, mock_client: AsyncMock, mock_config_entry: MockConfigEntry
) -> None:
    """Update-in-progress shortens the poll interval; percent fallback works."""
    mock_config_entry.add_to_hass(hass)
    mock_client.get_update_info = AsyncMock(
        return_value={
            "current_version": "0.6.11-beta.2",
            "latest_version": "0.6.12",
            "update_in_progress": True,
            "update_progress": {"percent": 55},
            "can_apply": True,
            "deployment": "docker",
        }
    )
    coordinator = SolarAiCoordinator(
        hass, config_entry=mock_config_entry, client=mock_client
    )
    data = await coordinator._async_update_data()
    assert data["pull_percent"] == 55
    assert coordinator.update_interval == UPDATE_POLL_INTERVAL
    assert isinstance(coordinator.update_interval, timedelta)
