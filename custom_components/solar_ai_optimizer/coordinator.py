"""DataUpdateCoordinator for Solar AI Optimizer."""

from __future__ import annotations

import logging

from aiohttp import ClientError, ClientResponseError
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import SolarAiClient
from .const import DEFAULT_SCAN_INTERVAL, DOMAIN, UPDATE_POLL_INTERVAL
from .models import CoordinatorData, SolarConfigData, UpdateData

_LOGGER = logging.getLogger(__name__)


class SolarAiCoordinator(DataUpdateCoordinator[CoordinatorData]):
    """Poll Solar health and system update endpoints."""

    config_entry: ConfigEntry

    def __init__(
        self,
        hass: HomeAssistant,
        *,
        config_entry: ConfigEntry,
        client: SolarAiClient,
    ) -> None:
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            config_entry=config_entry,
            update_interval=DEFAULT_SCAN_INTERVAL,
        )
        self.client = client
        self._update_in_progress = False

    @staticmethod
    def _format_error(err: BaseException) -> str:
        """Format aiohttp errors without relying on fragile __str__."""
        if isinstance(err, ClientResponseError):
            return f"HTTP {err.status}: {err.message}"
        return str(err)

    async def _async_update_data(self) -> CoordinatorData:
        """Fetch health always; update info when authorized."""
        try:
            health = await self.client.get_health()
        except ClientResponseError as err:
            if err.status == 401:
                raise ConfigEntryAuthFailed("Authentication failed") from err
            raise UpdateFailed(
                f"Error communicating with Solar API: {self._format_error(err)}"
            ) from err
        except ClientError as err:
            raise UpdateFailed(
                f"Error communicating with Solar API: {self._format_error(err)}"
            ) from err

        update: UpdateData | None = None
        config: SolarConfigData | None = None
        try:
            update = await self.client.get_update_info()
        except ClientResponseError as err:
            if err.status == 401:
                raise ConfigEntryAuthFailed("Authentication failed") from err
            raise UpdateFailed(
                f"Error fetching update info: {self._format_error(err)}"
            ) from err
        except ClientError as err:
            raise UpdateFailed(
                f"Error fetching update info: {self._format_error(err)}"
            ) from err

        try:
            config = await self.client.get_config()
        except ClientResponseError as err:
            # Config is best-effort for fail-safe amp defaults; update auth is authoritative.
            _LOGGER.debug(
                "Config fetch failed (status %s): %s",
                err.status,
                self._format_error(err),
            )
        except ClientError as err:
            _LOGGER.debug("Config fetch failed: %s", self._format_error(err))

        update = update or UpdateData()
        update_in_progress = bool(update.get("update_in_progress"))
        self._update_in_progress = update_in_progress
        self.update_interval = (
            UPDATE_POLL_INTERVAL if update_in_progress else DEFAULT_SCAN_INTERVAL
        )

        progress = update.get("update_progress") or {}
        pull_percent = progress.get("pull_percent")
        if pull_percent is None:
            pull_percent = progress.get("percent")

        return {
            "health": health,
            "update": update,
            "config": config,
            "install_id": health.get("install_id"),
            "version": health.get("version") or update.get("current_version"),
            "heartbeat_last_pulse": health.get("heartbeat_last_pulse"),
            "heartbeat_configured": health.get("heartbeat_configured"),
            "deployment": update.get("deployment"),
            "can_apply": bool(update.get("can_apply")),
            "update_in_progress": update_in_progress,
            "pull_percent": pull_percent,
            "release_notes": update.get("release_notes"),
            "latest_version": update.get("latest_version"),
            "current_version": update.get("current_version")
            or health.get("version"),
            "update_available": bool(update.get("update_available")),
            "apply_instructions": update.get("apply_instructions"),
            "release_url": update.get("release_url"),
        }
