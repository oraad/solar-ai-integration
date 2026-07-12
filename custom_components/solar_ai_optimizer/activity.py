"""Activity bridge for Solar AI Optimizer fail-safe events."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from homeassistant.components import logbook
from homeassistant.core import HomeAssistant, callback

from .const import DOMAIN

if TYPE_CHECKING:
    from .binary_sensor import SolarAiFailsafeBinarySensor
    from .event import SolarAiActivityEvent

LOGBOOK_NAME = "Solar AI Optimizer"


@dataclass
class SolarAiActivityBridge:
    """Coordinates fail-safe activity across event, logbook, and binary sensor."""

    hass: HomeAssistant
    event_entity: SolarAiActivityEvent | None = None
    failsafe_sensor: SolarAiFailsafeBinarySensor | None = None

    @callback
    def async_set_failsafe_active(self, active: bool) -> None:
        """Update the fail-safe active binary sensor."""
        if self.failsafe_sensor is not None:
            self.failsafe_sensor.async_set_latched(active)

    @callback
    def async_failsafe_activated(
        self, amps: float, switch_id: str, number_id: str
    ) -> None:
        """Record fail-safe activation in Activity."""
        attrs = {
            "max_amps": amps,
            "grid_charge_switch": switch_id,
            "max_current_number": number_id,
        }
        if self.event_entity is not None:
            self.event_entity.async_trigger_failsafe_activated(attrs)
        entity_id = (
            self.event_entity.entity_id if self.event_entity is not None else None
        )
        logbook.async_log_entry(
            self.hass,
            name=LOGBOOK_NAME,
            message=(
                f"Fail-safe: grid charge enabled at {amps} A (Solar disconnected)"
            ),
            domain=DOMAIN,
            entity_id=entity_id,
        )

    @callback
    def async_failsafe_cleared(self) -> None:
        """Record fail-safe latch cleared."""
        if self.event_entity is not None:
            self.event_entity.async_trigger_failsafe_cleared()
        self.async_set_failsafe_active(False)
        entity_id = (
            self.event_entity.entity_id if self.event_entity is not None else None
        )
        logbook.async_log_entry(
            self.hass,
            name=LOGBOOK_NAME,
            message="Fail-safe cleared: Solar connection restored",
            domain=DOMAIN,
            entity_id=entity_id,
        )
