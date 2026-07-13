"""The Solar AI Optimizer Home Assistant integration."""

from __future__ import annotations

from dataclasses import dataclass

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .activity import SolarAiActivityBridge
from .api import SolarAiClient, resolve_access_token
from .const import (
    AUTH_MODE_SUPERVISOR,
    CONF_HOST,
    CONF_VERIFY_SSL,
    PLATFORMS,
)
from .coordinator import SolarAiCoordinator
from .failsafe import SolarFailsafeWatchdog
from .repairs import async_check_failsafe_repair, failsafe_entity_ids


@dataclass
class SolarAiData:
    """Runtime data for a Solar AI Optimizer config entry."""

    coordinator: SolarAiCoordinator
    client: SolarAiClient
    activity: SolarAiActivityBridge
    auth_mode: str
    failsafe: SolarFailsafeWatchdog | None = None


type SolarAiConfigEntry = ConfigEntry[SolarAiData]


async def async_setup_entry(hass: HomeAssistant, entry: SolarAiConfigEntry) -> bool:
    """Set up Solar AI Optimizer from a config entry."""
    access_token, auth_mode = resolve_access_token(entry.data)
    if not access_token:
        if auth_mode == AUTH_MODE_SUPERVISOR:
            raise ConfigEntryNotReady(
                "SUPERVISOR_TOKEN is not available; will retry when the supervisor token becomes accessible"
            )
        raise ConfigEntryAuthFailed("Missing Solar AI Optimizer access token")

    session = async_get_clientsession(hass)
    client = SolarAiClient(
        host=entry.data[CONF_HOST],
        access_token=access_token,
        verify_ssl=entry.data.get(CONF_VERIFY_SSL, True),
        session=session,
    )
    coordinator = SolarAiCoordinator(
        hass, config_entry=entry, client=client
    )
    await coordinator.async_config_entry_first_refresh()

    data = SolarAiData(
        coordinator=coordinator,
        client=client,
        activity=SolarAiActivityBridge(hass),
        auth_mode=auth_mode,
    )
    entry.runtime_data = data

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    data.failsafe = await SolarFailsafeWatchdog.async_setup(
        hass, entry, coordinator, data.activity
    )

    switch_id, number_id = failsafe_entity_ids(entry.options, entry.data)
    async_check_failsafe_repair(
        hass, entry.entry_id, switch_id=switch_id, number_id=number_id
    )
    return True


async def async_unload_entry(hass: HomeAssistant, entry: SolarAiConfigEntry) -> bool:
    """Unload a config entry."""
    data = entry.runtime_data
    if data.failsafe is not None:
        data.failsafe.async_stop()
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
