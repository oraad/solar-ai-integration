"""Update platform for Solar AI Optimizer."""

from __future__ import annotations

from typing import Any

from aiohttp import ClientError, ClientResponseError
from homeassistant.components.update import (
    UpdateEntity,
    UpdateEntityFeature,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import SolarAiConfigEntry
from .const import DOMAIN
from .coordinator import SolarAiCoordinator
from .entity import SolarAiEntity

PARALLEL_UPDATES = 1


async def async_setup_entry(
    hass: HomeAssistant,
    entry: SolarAiConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the Solar AI update entity (always registered)."""
    _ = hass
    coordinator = entry.runtime_data.coordinator
    async_add_entities([SolarAiUpdateEntity(coordinator)])


class SolarAiUpdateEntity(SolarAiEntity, UpdateEntity):
    """Represent available Solar AI Optimizer software updates."""

    _attr_translation_key = "firmware"
    _attr_title = "Solar AI Optimizer"

    def __init__(self, coordinator: SolarAiCoordinator) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.config_entry.unique_id}_update"

    def _can_install(self) -> bool:
        data = self.coordinator.data or {}
        deployment = data.get("deployment")
        return bool(data.get("can_apply")) and deployment != "addon"

    @property
    def supported_features(self) -> UpdateEntityFeature:
        """Feature flags based on deployment / can_apply."""
        if self._can_install():
            return (
                UpdateEntityFeature.INSTALL
                | UpdateEntityFeature.PROGRESS
                | UpdateEntityFeature.RELEASE_NOTES
                | UpdateEntityFeature.SPECIFIC_VERSION
            )
        return UpdateEntityFeature.RELEASE_NOTES | UpdateEntityFeature.PROGRESS

    @property
    def installed_version(self) -> str | None:
        """Currently installed version."""
        if not self.coordinator.data:
            return None
        return self.coordinator.data.get("current_version") or self.coordinator.data.get(
            "version"
        )

    @property
    def latest_version(self) -> str | None:
        """Latest available version."""
        if not self.coordinator.data:
            return None
        return self.coordinator.data.get("latest_version")

    @property
    def release_url(self) -> str | None:
        """Release URL from the update API."""
        if not self.coordinator.data:
            return None
        return self.coordinator.data.get("release_url")

    @property
    def in_progress(self) -> bool | None:
        """Whether an update is in progress."""
        if not self.coordinator.data:
            return None
        return bool(self.coordinator.data.get("update_in_progress"))

    @property
    def update_percentage(self) -> int | float | None:
        """Pull progress percent when available."""
        if not self.coordinator.data:
            return None
        return self.coordinator.data.get("pull_percent")

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Expose apply instructions when INSTALL is unavailable."""
        data = self.coordinator.data or {}
        attrs: dict[str, Any] = {}
        if data.get("apply_instructions"):
            attrs["apply_instructions"] = data["apply_instructions"]
        if data.get("deployment"):
            attrs["deployment"] = data["deployment"]
        return attrs

    async def async_release_notes(self) -> str | None:
        """Return release notes from the last coordinator fetch."""
        if not self.coordinator.data:
            return None
        notes = self.coordinator.data.get("release_notes")
        return notes if isinstance(notes, str) else None

    async def async_install(
        self,
        version: str | None,
        backup: bool,
        **kwargs: Any,
    ) -> None:
        """Trigger Solar self-update."""
        _ = backup
        _ = kwargs
        client = self.coordinator.config_entry.runtime_data.client
        try:
            await client.apply_update(version=version)
        except ClientResponseError as err:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="update_failed",
                translation_placeholders={"error": str(err.status)},
            ) from err
        except ClientError as err:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="update_failed",
                translation_placeholders={"error": str(err)},
            ) from err
        await self.coordinator.async_request_refresh()
