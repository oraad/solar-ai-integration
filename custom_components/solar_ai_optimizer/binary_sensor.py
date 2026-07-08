"""Binary sensor platform for Solar AI Optimizer."""

from __future__ import annotations

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
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


async def async_setup_entry(
    hass: HomeAssistant,
    entry: SolarAiConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Solar AI binary sensors."""
    _ = hass
    coordinator = entry.runtime_data.coordinator
    async_add_entities([SolarAiHealthyBinarySensor(coordinator, entry)])


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
        pulse = parse_pulse(self.coordinator.data.get("heartbeat_last_pulse"))
        if pulse is None:
            return False
        age = (dt_util.utcnow() - dt_util.as_utc(pulse)).total_seconds()
        return age < self._stale_seconds()
