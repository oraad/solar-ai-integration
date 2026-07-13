"""Binary sensor platform for Solar AI Optimizer."""

from __future__ import annotations

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.const import STATE_ON, EntityCategory
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.restore_state import RestoreEntity
from homeassistant.util import dt as dt_util

from . import SolarAiConfigEntry
from .const import CONF_STALE_SECONDS, DEFAULT_STALE_SECONDS
from .coordinator import SolarAiCoordinator
from .entity import SolarAiEntity
from .helpers import parse_pulse

PARALLEL_UPDATES = 0

HEALTHY_SENSOR = BinarySensorEntityDescription(
    key="healthy",
    translation_key="healthy",
    device_class=BinarySensorDeviceClass.CONNECTIVITY,
)

FAILSAFE_ACTIVE_SENSOR = BinarySensorEntityDescription(
    key="failsafe_active",
    translation_key="failsafe_active",
    entity_category=EntityCategory.DIAGNOSTIC,
    icon="mdi:shield-alert",
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: SolarAiConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Solar AI binary sensors."""
    _ = hass
    coordinator = entry.runtime_data.coordinator
    failsafe_sensor = SolarAiFailsafeBinarySensor(coordinator, entry)
    entry.runtime_data.activity.failsafe_sensor = failsafe_sensor
    async_add_entities(
        [
            SolarAiHealthyBinarySensor(coordinator, entry),
            failsafe_sensor,
        ]
    )


class SolarAiHealthyBinarySensor(SolarAiEntity, BinarySensorEntity):
    """On when heartbeat pulse age is under the stale threshold."""

    entity_description = HEALTHY_SENSOR

    def __init__(
        self, coordinator: SolarAiCoordinator, entry: SolarAiConfigEntry
    ) -> None:
        super().__init__(coordinator)
        self._entry = entry
        self._attr_unique_id = f"{entry.unique_id}_healthy"

    def _stale_seconds(self) -> int:
        raw = self._entry.options.get(
            CONF_STALE_SECONDS,
            self._entry.data.get(CONF_STALE_SECONDS, DEFAULT_STALE_SECONDS),
        )
        try:
            return int(raw)
        except (TypeError, ValueError):
            return DEFAULT_STALE_SECONDS

    @property
    def is_on(self) -> bool | None:
        """Return True when the Solar heartbeat is fresh."""
        if not self.coordinator.data:
            return None
        if self.coordinator.data.get("heartbeat_configured") is False:
            # No heartbeat signal to judge freshness from — align with the
            # fail-safe watchdog, which treats this as healthy to avoid false alarms.
            return True
        pulse = parse_pulse(self.coordinator.data.get("heartbeat_last_pulse"))
        if pulse is None:
            return False
        age = (dt_util.utcnow() - dt_util.as_utc(pulse)).total_seconds()
        return age < self._stale_seconds()


class SolarAiFailsafeBinarySensor(SolarAiEntity, BinarySensorEntity, RestoreEntity):
    """On when the fail-safe latch is active."""

    entity_description = FAILSAFE_ACTIVE_SENSOR

    def __init__(
        self, coordinator: SolarAiCoordinator, entry: SolarAiConfigEntry
    ) -> None:
        super().__init__(coordinator)
        self._entry = entry
        self._latched = False
        self._attr_unique_id = f"{entry.unique_id}_failsafe_active"

    async def async_added_to_hass(self) -> None:
        """Restore latched state from last known entity state."""
        await super().async_added_to_hass()
        last_state = await self.async_get_last_state()
        if last_state is not None and last_state.state == STATE_ON:
            self._latched = True

    @property
    def available(self) -> bool:
        """Always available — the latch is local HA state, not Solar-derived."""
        return True

    @property
    def is_on(self) -> bool:
        """Return True when fail-safe is latched."""
        return self._latched

    @callback
    def async_set_latched(self, latched: bool) -> None:
        """Update latch state and refresh entity."""
        if self._latched == latched:
            return
        self._latched = latched
        self.async_write_ha_state()
