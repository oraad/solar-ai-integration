"""Lightweight tests that do not require a full HA runtime."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[3]
INTEGRATION = ROOT / "custom_components" / "solar_ai_optimizer"


def test_manifest_version_matches_version() -> None:
    """manifest.json version tracks VERSION."""
    version = (ROOT / "VERSION").read_text(encoding="utf-8").strip()
    manifest = json.loads((INTEGRATION / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["domain"] == "solar_ai_optimizer"
    assert manifest["version"] == version
    assert manifest["config_flow"] is True
    assert "quality_scale" not in manifest
    assert manifest["issue_tracker"] == "https://github.com/oraad/solar-ai-integration/issues"


def test_strings_and_translations_match() -> None:
    """translations/en.json stays in sync with strings.json."""
    strings = json.loads((INTEGRATION / "strings.json").read_text(encoding="utf-8"))
    en = json.loads(
        (INTEGRATION / "translations" / "en.json").read_text(encoding="utf-8")
    )
    assert strings == en


def test_hacs_zip_release_configured() -> None:
    """hacs.json uses zip_release with named asset."""
    hacs = json.loads((ROOT / "hacs.json").read_text(encoding="utf-8"))
    assert hacs["homeassistant"] == "2026.7.0"
    assert hacs["zip_release"] is True
    assert hacs["filename"] == "solar_ai_optimizer.zip"
    assert hacs["hide_default_branch"] is True


def test_client_strips_trailing_slash() -> None:
    """Host URLs should not keep a trailing slash."""
    pytest.importorskip("aiohttp")
    from custom_components.solar_ai_optimizer.api import SolarAiClient

    client = SolarAiClient(
        host="http://192.168.1.10:8000/",
        access_token="sol_c_test",
        verify_ssl=True,
        session=object(),  # type: ignore[arg-type]
    )
    assert client.host == "http://192.168.1.10:8000"


def test_domain_and_platforms() -> None:
    """Constants expose expected platforms."""
    pytest.importorskip("homeassistant")
    from custom_components.solar_ai_optimizer.const import (
        DEFAULT_SCAN_INTERVAL,
        DOMAIN,
        PLATFORMS,
    )

    assert DOMAIN == "solar_ai_optimizer"
    assert len(PLATFORMS) == 3
    assert DEFAULT_SCAN_INTERVAL.total_seconds() == 60
