"""Shared helpers for Solar AI Optimizer."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from homeassistant.util import dt as dt_util


def parse_pulse(value: object) -> datetime | None:
    """Parse a heartbeat pulse value into an aware datetime."""
    if value is None or value == "":
        return None
    if isinstance(value, datetime):
        if value.tzinfo is None:
            return dt_util.as_local(value)
        return value
    if isinstance(value, str):
        parsed = dt_util.parse_datetime(value)
        if parsed is None:
            return None
        if parsed.tzinfo is None:
            return dt_util.as_local(parsed)
        return parsed
    return None


def option_value(
    options: dict[str, Any],
    data: dict[str, Any],
    key: str,
    default: Any = None,
) -> Any:
    """Return an option preferring options over entry data."""
    if key in options:
        return options[key]
    return data.get(key, default)
