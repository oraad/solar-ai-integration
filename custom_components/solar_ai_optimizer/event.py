"""Event platform for Solar AI Optimizer."""

from __future__ import annotations

from typing import Any

from homeassistant.components.event import EventEntity
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import SolarAiConfigEntry
from .coordinator import SolarAiCoordinator
from .entity import SolarAiEntity

PARALLEL_UPDATES = 0

EVENT_FAILSAFE_ACTIVATED = "failsafe_activated"
EVENT_FAILSAFE_CLEARED = "failsafe_cleared"


async def async_setup_entry(
    hass: HomeAssistant,
    entry: SolarAiConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Solar AI event entities."""
    _ = hass
    coordinator = entry.runtime_data.coordinator
    entity = SolarAiActivityEvent(coordinator)
    entry.runtime_data.activity.event_entity = entity
    async_add_entities([entity])


class SolarAiActivityEvent(SolarAiEntity, EventEntity):
    """Reports integration activity (fail-safe events)."""

    _attr_translation_key = "integration_activity"
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_event_types = [EVENT_FAILSAFE_ACTIVATED, EVENT_FAILSAFE_CLEARED]

    def __init__(self, coordinator: SolarAiCoordinator) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = (
            f"{coordinator.config_entry.unique_id}_integration_activity"
        )

    @callback
    def async_trigger_failsafe_activated(self, attrs: dict[str, Any]) -> None:
        """Fire fail-safe activated event."""
        self._trigger_event(EVENT_FAILSAFE_ACTIVATED, attrs)
        self.async_write_ha_state()

    @callback
    def async_trigger_failsafe_cleared(self) -> None:
        """Fire fail-safe cleared event."""
        self._trigger_event(EVENT_FAILSAFE_CLEARED, {"reason": "heartbeat_restored"})
        self.async_write_ha_state()
