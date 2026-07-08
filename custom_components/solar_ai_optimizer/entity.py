"""Entity base for Solar AI Optimizer."""

from __future__ import annotations

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import CONF_HOST, CONF_INSTALL_ID, DOMAIN
from .coordinator import SolarAiCoordinator


class SolarAiEntity(CoordinatorEntity[SolarAiCoordinator]):
    """Base entity tied to the Solar install device."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: SolarAiCoordinator) -> None:
        super().__init__(coordinator)
        entry = coordinator.config_entry
        install_id = (
            entry.data.get(CONF_INSTALL_ID)
            or (coordinator.data or {}).get("install_id")
            or entry.unique_id
            or entry.entry_id
        )
        host = entry.data.get(CONF_HOST, "")
        self._install_id = str(install_id)
        self._configuration_url = host or None

    @property
    def device_info(self) -> DeviceInfo:
        """Return device info with software version from coordinator."""
        version = None
        if self.coordinator.data:
            version = self.coordinator.data.get("version")
        return DeviceInfo(
            identifiers={(DOMAIN, self._install_id)},
            manufacturer="Oraad",
            model="Solar AI Optimizer",
            name="Solar AI Optimizer",
            configuration_url=self._configuration_url,
            sw_version=version,
        )