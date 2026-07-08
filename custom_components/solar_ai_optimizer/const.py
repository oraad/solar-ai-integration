"""Constants for the Solar AI Optimizer integration."""

from __future__ import annotations

from datetime import timedelta

from homeassistant.const import Platform

DOMAIN = "solar_ai_optimizer"

CONF_HOST = "host"
CONF_VERIFY_SSL = "verify_ssl"
CONF_ACCESS_TOKEN = "access_token"
CONF_CLIENT_ID = "client_id"
CONF_INSTALL_ID = "install_id"
CONF_GRID_CHARGE_ENABLE = "grid_charge_enable"
CONF_MAX_GRID_CHARGE_CURRENT = "max_grid_charge_current"
CONF_STALE_SECONDS = "stale_seconds"
CONF_DEBOUNCE_SECONDS = "debounce_seconds"
CONF_PAIR_CODE = "pair_code"

DEFAULT_STALE_SECONDS = 120
DEFAULT_DEBOUNCE_SECONDS = 120
DEFAULT_MAX_GRID_CHARGE_A = 60.0
DEFAULT_SCAN_INTERVAL = timedelta(seconds=60)
UPDATE_POLL_INTERVAL = timedelta(seconds=2)

PLATFORMS: list[Platform] = [
    Platform.SENSOR,
    Platform.BINARY_SENSOR,
    Platform.UPDATE,
]
