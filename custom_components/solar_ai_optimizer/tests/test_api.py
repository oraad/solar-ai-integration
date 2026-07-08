"""API client unit tests."""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest
from aiohttp import ClientError, ClientResponseError

from custom_components.solar_ai_optimizer.api import SolarAiClient


@pytest.fixture
def session() -> MagicMock:
    """Mock aiohttp ClientSession."""
    return MagicMock()


def _response(payload: Any, *, status: int = 200) -> AsyncMock:
    resp = AsyncMock()
    resp.status = status
    resp.raise_for_status = MagicMock()
    resp.json = AsyncMock(return_value=payload)
    resp.__aenter__ = AsyncMock(return_value=resp)
    resp.__aexit__ = AsyncMock(return_value=None)
    return resp


async def test_get_health_and_update(session: MagicMock) -> None:
    """Client GETs health and update endpoints."""
    health = {"install_id": "x", "version": "1.0.0"}
    update = {"current_version": "1.0.0", "can_apply": False}
    session.request = MagicMock(
        side_effect=[
            _response(health),
            _response(update),
            _response({"grid_charge": {}}),
            _response(None, status=204),
        ]
    )
    client = SolarAiClient("http://host:8000/", "tok", True, session)
    assert client.host == "http://host:8000"
    assert await client.get_health() == health
    assert await client.get_update_info(refresh=True) == update
    assert await client.get_config() == {"grid_charge": {}}
    assert await client._request("POST", "/noop") is None
    # Empty token path
    bare = SolarAiClient("http://host:8000", "", True, session)
    assert "Authorization" not in bare._headers()


async def test_apply_update_and_redeem(session: MagicMock) -> None:
    """Client POSTs update and pair redeem."""
    session.request = MagicMock(
        side_effect=[
            _response({"ok": True}),
            _response({"access_token": "t", "client_id": "c"}),
            _response(["not", "a", "dict"]),
        ]
    )
    client = SolarAiClient("http://host:8000", "tok", False, session)
    assert await client.apply_update(version="1.2.3") == {"ok": True}
    redeemed = await client.redeem_pair("ABCD-1234")
    assert redeemed["access_token"] == "t"
    assert await client._request("GET", "/x") == {}


async def test_request_raises_response_error(session: MagicMock) -> None:
    """HTTP errors propagate."""
    resp = _response(None, status=500)
    resp.raise_for_status = MagicMock(
        side_effect=ClientResponseError(
            request_info=None,  # type: ignore[arg-type]
            history=(),
            status=500,
            message="err",
        )
    )
    session.request = MagicMock(return_value=resp)
    client = SolarAiClient("http://host:8000", "", True, session)
    with pytest.raises(ClientResponseError):
        await client.get_health()


async def test_request_raises_client_error(session: MagicMock) -> None:
    """Transport errors propagate."""
    session.request = MagicMock(side_effect=ClientError("boom"))
    client = SolarAiClient("http://host:8000", "tok", True, session)
    with pytest.raises(ClientError):
        await client.get_health()
