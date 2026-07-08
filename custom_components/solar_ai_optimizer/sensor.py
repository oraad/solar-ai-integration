"""Sensor platform for Solar AI Optimizer."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
)
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.typing import StateType

from . import SolarAiConfigEntry
from .coordinator import SolarAiCoordinator
from .entity import SolarAiEntity
from .helpers import parse_pulse
from .models import CoordinatorData

PARALLEL_UPDATES = 0


@dataclass(frozen=True, kw_only=True)
class SolarAiSensorEntityDescription(SensorEntityDescription):
    """Describes a Solar AI sensor."""

    value_fn: Callable[[CoordinatorData], StateType | datetime]


SENSORS: tuple[SolarAiSensorEntityDescription, ...] = (
    SolarAiSensorEntityDescription(
        key="version",
        translation_key="version",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda data: data.get("version"),
    ),
    SolarAiSensorEntityDescription(
        key="last_pulse",
        translation_key="last_pulse",
        device_class=SensorDeviceClass.TIMESTAMP,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda data: parse_pulse(data.get("heartbeat_last_pulse")),
    ),
    SolarAiSensorEntityDescription(
        key="install_visibility",
        translation_key="install_visibility",
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        value_fn=lambda data: data.get("install_id"),
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: SolarAiConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Solar AI sensors."""
    _ = hass
    coordinator = entry.runtime_data.coordinator
    async_add_entities(
        SolarAiSensor(coordinator, description) for description in SENSORS
    )


class SolarAiSensor(SolarAiEntity, SensorEntity):
    """Sensor backed by coordinator data."""

    entity_description: SolarAiSensorEntityDescription

    def __init__(
        self,
        coordinator: SolarAiCoordinator,
        description: SolarAiSensorEntityDescription,
    ) -> None:
        super().__init__(coordinator)
        self.entity_description = description
        self._attr_unique_id = (
            f"{coordinator.config_entry.unique_id}_{description.key}"
        )

    @property
    def native_value(self) -> StateType | datetime:
        """Return the sensor value."""
        if not self.coordinator.data:
            return None
        return self.entity_description.value_fn(self.coordinator.data)
