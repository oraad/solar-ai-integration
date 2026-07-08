"""Shared fixtures for Solar AI Optimizer integration tests."""

from __future__ import annotations

from collections.abc import Generator
from typing import Any
from unittest.mock import AsyncMock, patch

import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.solar_ai_optimizer.const import (
    CONF_ACCESS_TOKEN,
    CONF_HOST,
    CONF_INSTALL_ID,
    CONF_VERIFY_SSL,
    DOMAIN,
)

pytest_plugins = "pytest_homeassistant_custom_component"


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations: None) -> None:
    """Enable loading custom integrations in every test."""
    return None


@pytest.fixture(autouse=True)
def expected_lingering_timers() -> bool:
    """Coordinators schedule refresh interval timers that outlive the test."""
    return True


@pytest.fixture
def mock_health() -> dict[str, Any]:
    """Sample health payload."""
    return {
        "install_id": "install-abc12345",
        "version": "0.6.11-beta.2",
        "heartbeat_last_pulse": "2026-07-08T10:00:00+00:00",
        "heartbeat_configured": True,
    }


@pytest.fixture
def mock_update() -> dict[str, Any]:
    """Sample update payload."""
    return {
        "current_version": "0.6.11-beta.2",
        "latest_version": "0.6.12",
        "update_available": True,
        "update_in_progress": False,
        "can_apply": True,
        "deployment": "docker",
        "release_notes": "Bug fixes",
        "release_url": "https://github.com/oraad/solar-ai-optimizer/releases",
    }


@pytest.fixture
def mock_config() -> dict[str, Any]:
    """Sample Solar config payload."""
    return {"grid_charge": {"max_grid_charge_a": 40}}


@pytest.fixture
def mock_client(
    mock_health: dict[str, Any],
    mock_update: dict[str, Any],
    mock_config: dict[str, Any],
) -> Generator[AsyncMock]:
    """Patch SolarAiClient methods used by setup and coordinator."""
    client = AsyncMock()
    client.host = "http://192.168.1.10:8000"
    client.get_health = AsyncMock(return_value=mock_health)
    client.get_update_info = AsyncMock(return_value=mock_update)
    client.get_config = AsyncMock(return_value=mock_config)
    client.apply_update = AsyncMock(return_value=mock_update)
    client.redeem_pair = AsyncMock(
        return_value={
            "access_token": "sol_c_test_token",
            "client_id": "client-1",
            "install_id": mock_health["install_id"],
        }
    )
    with patch(
        "custom_components.solar_ai_optimizer.SolarAiClient",
        return_value=client,
    ), patch(
        "custom_components.solar_ai_optimizer.coordinator.SolarAiClient",
        return_value=client,
    ), patch(
        "custom_components.solar_ai_optimizer.api.SolarAiClient",
        return_value=client,
    ), patch(
        "custom_components.solar_ai_optimizer.config_flow.SolarAiClient",
        return_value=client,
    ), patch(
        "custom_components.solar_ai_optimizer.__init__.SolarAiClient",
        return_value=client,
    ):
        yield client


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Return a MockConfigEntry for Solar AI Optimizer."""
    return MockConfigEntry(
        domain=DOMAIN,
        title="Solar AI Optimizer (install-)",
        data={
            CONF_HOST: "http://192.168.1.10:8000",
            CONF_VERIFY_SSL: True,
            CONF_ACCESS_TOKEN: "sol_c_test_token",
            CONF_INSTALL_ID: "install-abc12345",
            "client_id": "client-1",
        },
        unique_id="install-abc12345",
    )
