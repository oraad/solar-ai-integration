"""Init and diagnostics tests."""

from __future__ import annotations

from unittest.mock import AsyncMock

from homeassistant.core import HomeAssistant
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.solar_ai_optimizer.const import DOMAIN
from custom_components.solar_ai_optimizer.diagnostics import (
    async_get_config_entry_diagnostics,
)


async def test_setup_and_unload(
    hass: HomeAssistant, mock_client: AsyncMock, mock_config_entry: MockConfigEntry
) -> None:
    """Config entry sets up platforms and unloads cleanly."""
    mock_config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    assert mock_config_entry.runtime_data.coordinator.data is not None
    assert await hass.config_entries.async_unload(mock_config_entry.entry_id)


async def test_diagnostics_redacts_token(
    hass: HomeAssistant, mock_client: AsyncMock, mock_config_entry: MockConfigEntry
) -> None:
    """Diagnostics redact the access token."""
    mock_config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    diag = await async_get_config_entry_diagnostics(hass, mock_config_entry)
    assert diag["entry"]["data"]["access_token"] == "**REDACTED**"
    assert diag["entry"]["unique_id"] == "install-abc12345"
    assert DOMAIN
