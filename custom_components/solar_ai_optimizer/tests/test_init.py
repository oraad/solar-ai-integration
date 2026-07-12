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
    """Diagnostics redact the access token and expose auth_mode."""
    mock_config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    diag = await async_get_config_entry_diagnostics(hass, mock_config_entry)
    assert diag["entry"]["data"]["access_token"] == "**REDACTED**"
    assert diag["entry"]["unique_id"] == "install-abc12345"
    assert diag["entry"]["auth_mode"] == "token"
    assert diag["failsafe"]["max_grid_charge_amps"] == 40.0
    assert DOMAIN


async def test_setup_supervisor_auth(
    hass: HomeAssistant, mock_client: AsyncMock, monkeypatch
) -> None:
    """Supervisor auth_mode resolves SUPERVISOR_TOKEN at runtime."""
    from pytest_homeassistant_custom_component.common import MockConfigEntry

    from custom_components.solar_ai_optimizer.const import (
        AUTH_MODE_SUPERVISOR,
        CONF_AUTH_MODE,
        CONF_HOST,
        CONF_INSTALL_ID,
        CONF_VERIFY_SSL,
    )

    monkeypatch.setenv("SUPERVISOR_TOKEN", "supervisor-secret")
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Solar AI Optimizer",
        data={
            CONF_HOST: "http://solar-ai-optimizer:8000",
            CONF_VERIFY_SSL: True,
            CONF_AUTH_MODE: AUTH_MODE_SUPERVISOR,
            CONF_INSTALL_ID: "install-abc12345",
        },
        unique_id="install-abc12345",
    )
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    assert entry.runtime_data.auth_mode == AUTH_MODE_SUPERVISOR
    assert await hass.config_entries.async_unload(entry.entry_id)


async def test_setup_missing_supervisor_token(
    hass: HomeAssistant, monkeypatch
) -> None:
    """Supervisor auth without SUPERVISOR_TOKEN fails setup."""
    from pytest_homeassistant_custom_component.common import MockConfigEntry

    from custom_components.solar_ai_optimizer.const import (
        AUTH_MODE_SUPERVISOR,
        CONF_AUTH_MODE,
        CONF_HOST,
        CONF_INSTALL_ID,
        CONF_VERIFY_SSL,
    )

    monkeypatch.delenv("SUPERVISOR_TOKEN", raising=False)
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Solar AI Optimizer",
        data={
            CONF_HOST: "http://solar-ai-optimizer:8000",
            CONF_VERIFY_SSL: True,
            CONF_AUTH_MODE: AUTH_MODE_SUPERVISOR,
            CONF_INSTALL_ID: "install-abc12345",
        },
        unique_id="install-abc12345",
    )
    entry.add_to_hass(hass)
    assert not await hass.config_entries.async_setup(entry.entry_id)