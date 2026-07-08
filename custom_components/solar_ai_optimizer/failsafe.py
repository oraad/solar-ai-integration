"""Fail-safe watchdog that acts when Solar heartbeat goes stale."""

from __future__ import annotations

import logging
from datetime import datetime, timedelta
from typing import TYPE_CHECKING, Any, TypeVar

from homeassistant.const import ATTR_ENTITY_ID
from homeassistant.core import CALLBACK_TYPE, HomeAssistant, callback
from homeassistant.helpers.event import async_track_time_interval
from homeassistant.util import dt as dt_util

from .const import (
    CONF_DEBOUNCE_SECONDS,
    CONF_GRID_CHARGE_ENABLE,
    CONF_MAX_GRID_CHARGE_CURRENT,
    CONF_STALE_SECONDS,
    DEFAULT_DEBOUNCE_SECONDS,
    DEFAULT_MAX_GRID_CHARGE_A,
    DEFAULT_STALE_SECONDS,
)
from .helpers import option_value, parse_pulse

if TYPE_CHECKING:
    from . import SolarAiConfigEntry
    from .coordinator import SolarAiCoordinator

_LOGGER = logging.getLogger(__name__)

_TICK = timedelta(seconds=15)

_T = TypeVar("_T")


def _option(entry: SolarAiConfigEntry, key: str, default: _T | None = None) -> Any:
    return option_value(dict(entry.options), dict(entry.data), key, default)


class SolarFailsafeWatchdog:
    """Latch grid-charge fail-safe when Solar heartbeat is stale."""

    def __init__(
        self,
        hass: HomeAssistant,
        entry: SolarAiConfigEntry,
        coordinator: SolarAiCoordinator,
    ) -> None:
        self.hass = hass
        self.entry = entry
        self.coordinator = coordinator
        self._unhealthy_since: datetime | None = None
        self._latched = False
        self._unsubs: list[CALLBACK_TYPE] = []

    @classmethod
    async def async_setup(
        cls,
        hass: HomeAssistant,
        entry: SolarAiConfigEntry,
        coordinator: SolarAiCoordinator,
    ) -> SolarFailsafeWatchdog | None:
        """Start the watchdog if grid-charge entities are configured."""
        switch_id = _option(entry, CONF_GRID_CHARGE_ENABLE)
        number_id = _option(entry, CONF_MAX_GRID_CHARGE_CURRENT)
        if not switch_id or not number_id:
            _LOGGER.debug("Fail-safe entities not configured; watchdog idle")
            return None
        watchdog = cls(hass, entry, coordinator)
        await watchdog.async_start()
        return watchdog

    async def async_start(self) -> None:
        """Subscribe to coordinator updates and a periodic tick."""
        self._unsubs.append(
            self.coordinator.async_add_listener(self._on_coordinator_update)
        )
        self._unsubs.append(
            async_track_time_interval(self.hass, self._on_tick, _TICK)
        )
        self._evaluate()

    @callback
    def async_stop(self) -> None:
        """Unsubscribe listeners."""
        while self._unsubs:
            self._unsubs.pop()()

    @callback
    def _on_coordinator_update(self) -> None:
        self._evaluate()

    @callback
    def _on_tick(self, _now: datetime) -> None:
        self._evaluate()

    def _stale_seconds(self) -> int:
        raw = _option(self.entry, CONF_STALE_SECONDS, DEFAULT_STALE_SECONDS)
        try:
            return int(raw)
        except (TypeError, ValueError):
            return DEFAULT_STALE_SECONDS

    def _debounce_seconds(self) -> int:
        raw = _option(self.entry, CONF_DEBOUNCE_SECONDS, DEFAULT_DEBOUNCE_SECONDS)
        try:
            return int(raw)
        except (TypeError, ValueError):
            return DEFAULT_DEBOUNCE_SECONDS

    def _is_healthy(self) -> bool:
        data = self.coordinator.data or {}
        pulse = parse_pulse(data.get("heartbeat_last_pulse"))
        if pulse is None:
            return False
        age = (dt_util.utcnow() - dt_util.as_utc(pulse)).total_seconds()
        return age < self._stale_seconds()

    def _max_amps(self) -> float:
        data = self.coordinator.data or {}
        config = data.get("config") or {}
        grid = config.get("grid_charge") if isinstance(config, dict) else None
        if isinstance(grid, dict) and grid.get("max_grid_charge_a") is not None:
            try:
                return float(grid["max_grid_charge_a"])
            except (TypeError, ValueError):
                pass
        return DEFAULT_MAX_GRID_CHARGE_A

    @callback
    def _evaluate(self) -> None:
        healthy = self._is_healthy()
        now = dt_util.utcnow()

        if healthy:
            if self._latched:
                _LOGGER.info("Solar heartbeat healthy again; clearing fail-safe latch")
            self._latched = False
            self._unhealthy_since = None
            return

        if self._unhealthy_since is None:
            self._unhealthy_since = now

        if self._latched:
            return

        elapsed = (now - self._unhealthy_since).total_seconds()
        if elapsed < self._debounce_seconds():
            return

        self._latched = True
        self.hass.async_create_task(self._async_apply_failsafe())

    async def _async_apply_failsafe(self) -> None:
        switch_id = _option(self.entry, CONF_GRID_CHARGE_ENABLE)
        number_id = _option(self.entry, CONF_MAX_GRID_CHARGE_CURRENT)
        amps = self._max_amps()
        _LOGGER.warning(
            "Solar heartbeat stale beyond debounce; enabling grid charge "
            "(%s) at %s A via %s",
            switch_id,
            amps,
            number_id,
        )
        try:
            await self.hass.services.async_call(
                "switch",
                "turn_on",
                {ATTR_ENTITY_ID: switch_id},
                blocking=True,
            )
            await self.hass.services.async_call(
                "number",
                "set_value",
                {ATTR_ENTITY_ID: number_id, "value": amps},
                blocking=True,
            )
        except Exception:  # noqa: BLE001
            _LOGGER.exception(
                "Fail-safe service calls failed for switch=%s number=%s",
                switch_id,
                number_id,
            )
