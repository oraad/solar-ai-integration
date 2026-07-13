"""HTTP client for the Solar AI Optimizer API."""

from __future__ import annotations

import os
from collections.abc import Mapping
from typing import Any, cast

from aiohttp import ClientError, ClientResponseError, ClientSession, ClientTimeout

_REQUEST_TIMEOUT = ClientTimeout(total=30)

from .const import (
    AUTH_MODE_NONE,
    AUTH_MODE_SUPERVISOR,
    AUTH_MODE_TOKEN,
    CONF_ACCESS_TOKEN,
    CONF_AUTH_MODE,
    ENV_SUPERVISOR_TOKEN,
)
from .models import HealthData, SolarConfigData, UpdateData


def resolve_access_token(entry_data: Mapping[str, Any]) -> tuple[str, str]:
    """Resolve bearer token and auth mode for a config entry.

    Priority: stored pairing token (``sol_c_*``) → ``SUPERVISOR_TOKEN`` when
    ``auth_mode=supervisor`` → empty token with mode ``none``.
    """
    stored = str(entry_data.get(CONF_ACCESS_TOKEN) or "").strip()
    if stored:
        return stored, AUTH_MODE_TOKEN

    if entry_data.get(CONF_AUTH_MODE) == AUTH_MODE_SUPERVISOR:
        supervisor = os.environ.get(ENV_SUPERVISOR_TOKEN, "").strip()
        if supervisor:
            return supervisor, AUTH_MODE_SUPERVISOR
        return "", AUTH_MODE_SUPERVISOR

    return "", AUTH_MODE_NONE


class SolarAiClient:
    """Async HTTP client talking to a Solar AI Optimizer instance."""

    def __init__(
        self,
        host: str,
        access_token: str,
        verify_ssl: bool,
        session: ClientSession,
    ) -> None:
        self._host = host.rstrip("/")
        self._access_token = access_token
        self._verify_ssl = verify_ssl
        self._session = session

    @property
    def host(self) -> str:
        """Return the base host URL without a trailing slash."""
        return self._host

    def _headers(self) -> dict[str, str]:
        headers: dict[str, str] = {"Accept": "application/json"}
        if self._access_token:
            headers["Authorization"] = f"Bearer {self._access_token}"
        return headers

    async def _request(
        self,
        method: str,
        path: str,
        *,
        json: dict[str, object] | None = None,
        params: dict[str, str] | None = None,
        auth: bool = True,
    ) -> dict[str, Any] | None:
        url = f"{self._host}{path}"
        headers = self._headers() if auth else {"Accept": "application/json"}
        try:
            async with self._session.request(
                method,
                url,
                headers=headers,
                json=json,
                params=params,
                ssl=self._verify_ssl,
                timeout=_REQUEST_TIMEOUT,
            ) as response:
                response.raise_for_status()
                if response.status == 204:
                    return None
                payload = await response.json(content_type=None)
                if isinstance(payload, dict):
                    return cast(dict[str, Any], payload)
                return {}
        except ClientResponseError:
            raise
        except ClientError:
            raise

    async def get_health(self) -> HealthData:
        """GET /api/health (no auth required on the Solar side)."""
        return cast(HealthData, await self._request("GET", "/api/health", auth=False))

    async def get_me(self) -> dict[str, Any]:
        """GET /api/me (requires a valid bearer token)."""
        return cast(dict[str, Any], await self._request("GET", "/api/me"))

    async def get_update_info(self, refresh: bool = False) -> UpdateData:
        """GET /api/system/update."""
        params = {"refresh": "true"} if refresh else None
        return cast(
            UpdateData,
            await self._request("GET", "/api/system/update", params=params),
        )

    async def apply_update(self, version: str | None = None) -> UpdateData:
        """POST /api/system/update."""
        body: dict[str, object] = {}
        if version is not None:
            body["version"] = version
        return cast(
            UpdateData,
            await self._request("POST", "/api/system/update", json=body or None),
        )

    async def get_config(self) -> SolarConfigData:
        """GET /api/config."""
        return cast(SolarConfigData, await self._request("GET", "/api/config"))

    async def redeem_pair(
        self,
        code: str,
        client_name: str = "Home Assistant",
    ) -> dict[str, Any]:
        """POST /api/pair/redeem."""
        return cast(
            dict[str, Any],
            await self._request(
                "POST",
                "/api/pair/redeem",
                json={"code": code, "client_name": client_name},
                auth=False,
            ),
        )
