"""Typed coordinator payloads for Solar AI Optimizer."""

from __future__ import annotations

from typing import NotRequired, TypedDict


class HealthData(TypedDict, total=False):
    """Subset of GET /api/health used by the integration."""

    install_id: str
    version: str
    heartbeat_last_pulse: str | None
    heartbeat_configured: bool


class UpdateProgressData(TypedDict, total=False):
    """Nested progress block from GET /api/system/update."""

    pull_percent: int | float
    percent: int | float


class UpdateData(TypedDict, total=False):
    """Subset of GET /api/system/update."""

    current_version: str
    latest_version: str
    update_available: bool
    update_in_progress: bool
    update_progress: UpdateProgressData
    can_apply: bool
    deployment: str
    release_notes: str
    release_url: str
    apply_instructions: str


class GridChargeConfig(TypedDict, total=False):
    """Grid charge settings from GET /api/config."""

    max_grid_charge_a: float | int


class SolarConfigData(TypedDict, total=False):
    """Subset of GET /api/config."""

    grid_charge: GridChargeConfig


class CoordinatorData(TypedDict):
    """Aggregated coordinator snapshot for entities and fail-safe."""

    health: HealthData
    update: UpdateData
    config: SolarConfigData | None
    install_id: NotRequired[str | None]
    version: NotRequired[str | None]
    heartbeat_last_pulse: NotRequired[str | None]
    heartbeat_configured: NotRequired[bool | None]
    deployment: NotRequired[str | None]
    can_apply: bool
    update_in_progress: bool
    pull_percent: NotRequired[int | float | None]
    release_notes: NotRequired[str | None]
    latest_version: NotRequired[str | None]
    current_version: NotRequired[str | None]
    update_available: bool
    apply_instructions: NotRequired[str | None]
    release_url: NotRequired[str | None]
