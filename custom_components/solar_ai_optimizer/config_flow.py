"""Config flow for Solar AI Optimizer."""

from __future__ import annotations

import logging
import os
from typing import Any

from aiohttp import ClientError, ClientResponseError
import voluptuous as vol

from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlowWithReload,
)
from homeassistant.core import callback
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.selector import (
    EntitySelector,
    EntitySelectorConfig,
    NumberSelector,
    NumberSelectorConfig,
    NumberSelectorMode,
)
from homeassistant.helpers.service_info.hassio import HassioServiceInfo
from homeassistant.helpers.service_info.zeroconf import ZeroconfServiceInfo

from .api import SolarAiClient, resolve_access_token
from .const import (
    AUTH_MODE_SUPERVISOR,
    AUTH_MODE_TOKEN,
    CONF_ACCESS_TOKEN,
    CONF_AUTH_MODE,
    CONF_CLIENT_ID,
    CONF_DEBOUNCE_SECONDS,
    CONF_GRID_CHARGE_ENABLE,
    CONF_HOST,
    CONF_INSTALL_ID,
    CONF_MAX_GRID_CHARGE_CURRENT,
    CONF_PAIR_CODE,
    CONF_STALE_SECONDS,
    CONF_VERIFY_SSL,
    DEFAULT_DEBOUNCE_SECONDS,
    DEFAULT_HTTP_PORT,
    DEFAULT_STALE_SECONDS,
    DOMAIN,
    ENV_SUPERVISOR_TOKEN,
)
from .repairs import async_check_failsafe_repair, failsafe_entity_ids

_LOGGER = logging.getLogger(__name__)

USER_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_HOST): str,
        vol.Required(CONF_PAIR_CODE): str,
        vol.Optional(CONF_VERIFY_SSL, default=True): bool,
        vol.Optional(CONF_GRID_CHARGE_ENABLE): EntitySelector(
            EntitySelectorConfig(domain="switch")
        ),
        vol.Optional(CONF_MAX_GRID_CHARGE_CURRENT): EntitySelector(
            EntitySelectorConfig(domain="number")
        ),
        vol.Optional(CONF_STALE_SECONDS, default=DEFAULT_STALE_SECONDS): NumberSelector(
            NumberSelectorConfig(
                min=30, max=600, step=10, mode=NumberSelectorMode.BOX, unit_of_measurement="s"
            )
        ),
        vol.Optional(
            CONF_DEBOUNCE_SECONDS, default=DEFAULT_DEBOUNCE_SECONDS
        ): NumberSelector(
            NumberSelectorConfig(
                min=30, max=600, step=10, mode=NumberSelectorMode.BOX, unit_of_measurement="s"
            )
        ),
    }
)

REAUTH_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_PAIR_CODE): str,
    }
)

RECONFIGURE_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_HOST): str,
        vol.Optional(CONF_VERIFY_SSL, default=True): bool,
    }
)

OPTIONS_SCHEMA = vol.Schema(
    {
        vol.Optional(CONF_GRID_CHARGE_ENABLE): EntitySelector(
            EntitySelectorConfig(domain="switch")
        ),
        vol.Optional(CONF_MAX_GRID_CHARGE_CURRENT): EntitySelector(
            EntitySelectorConfig(domain="number")
        ),
        vol.Optional(CONF_STALE_SECONDS, default=DEFAULT_STALE_SECONDS): NumberSelector(
            NumberSelectorConfig(
                min=30, max=600, step=10, mode=NumberSelectorMode.BOX, unit_of_measurement="s"
            )
        ),
        vol.Optional(
            CONF_DEBOUNCE_SECONDS, default=DEFAULT_DEBOUNCE_SECONDS
        ): NumberSelector(
            NumberSelectorConfig(
                min=30, max=600, step=10, mode=NumberSelectorMode.BOX, unit_of_measurement="s"
            )
        ),
    }
)


def _failsafe_options(user_input: dict[str, Any]) -> dict[str, Any]:
    """Extract optional fail-safe fields from a user step submission."""
    return {
        key: user_input[key]
        for key in (
            CONF_GRID_CHARGE_ENABLE,
            CONF_MAX_GRID_CHARGE_CURRENT,
            CONF_STALE_SECONDS,
            CONF_DEBOUNCE_SECONDS,
        )
        if key in user_input and user_input[key] not in (None, "")
    }


class SolarAiConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Solar AI Optimizer."""

    VERSION = 1

    def __init__(self) -> None:
        self._reauth_entry: ConfigEntry | None = None
        self._hassio_discovery: HassioServiceInfo | None = None
        self._discovered_host: str | None = None

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> SolarAiOptionsFlow:
        """Create the options flow."""
        return SolarAiOptionsFlow()

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial user step (manual or post-zeroconf pairing)."""
        errors: dict[str, str] = {}

        if user_input is not None:
            host = str(user_input[CONF_HOST]).strip().rstrip("/")
            verify_ssl = bool(user_input.get(CONF_VERIFY_SSL, True))
            pair_code = str(user_input.get(CONF_PAIR_CODE) or "").strip()

            if not pair_code:
                errors["base"] = "invalid_auth"
            else:
                session = async_get_clientsession(self.hass)
                client = SolarAiClient(
                    host=host,
                    access_token="",
                    verify_ssl=verify_ssl,
                    session=session,
                )

                try:
                    health = await client.get_health()
                except ClientError:
                    errors["base"] = "cannot_connect"
                except Exception:  # noqa: BLE001
                    _LOGGER.exception("Unexpected error probing Solar health")
                    errors["base"] = "unknown"
                else:
                    install_id = health.get("install_id")
                    token: str | None = None
                    client_id: str | None = None

                    try:
                        redeemed = await client.redeem_pair(pair_code)
                        token = redeemed.get("access_token")
                        client_id = redeemed.get("client_id")
                        install_id = redeemed.get("install_id") or install_id
                    except ClientResponseError as err:
                        if err.status in (400, 409):
                            errors["base"] = "invalid_pair_code"
                        elif err.status == 401:
                            errors["base"] = "invalid_auth"
                        else:
                            errors["base"] = "cannot_connect"
                    except ClientError:
                        errors["base"] = "cannot_connect"

                    if not errors and token:
                        auth_client = SolarAiClient(
                            host=host,
                            access_token=token,
                            verify_ssl=verify_ssl,
                            session=session,
                        )
                        try:
                            await auth_client.get_me()
                        except ClientResponseError as err:
                            if err.status == 401:
                                errors["base"] = "invalid_auth"
                            else:
                                errors["base"] = "cannot_connect"
                        except ClientError:
                            errors["base"] = "cannot_connect"
                        except Exception:  # noqa: BLE001
                            _LOGGER.exception("Unexpected error validating pair token")
                            errors["base"] = "unknown"

                    if not errors:
                        if token and install_id:
                            await self.async_set_unique_id(str(install_id))
                            self._abort_if_unique_id_configured()

                            data = {
                                CONF_HOST: host,
                                CONF_VERIFY_SSL: verify_ssl,
                                CONF_ACCESS_TOKEN: token,
                                CONF_AUTH_MODE: AUTH_MODE_TOKEN,
                                CONF_CLIENT_ID: client_id,
                                CONF_INSTALL_ID: str(install_id),
                            }
                            title = f"Solar AI Optimizer ({str(install_id)[:8]})"
                            return self.async_create_entry(
                                title=title,
                                data=data,
                                options=_failsafe_options(user_input),
                            )
                        errors["base"] = "unknown"

        suggested: dict[str, Any] = {}
        if self._discovered_host:
            suggested[CONF_HOST] = self._discovered_host

        return self.async_show_form(
            step_id="user",
            data_schema=self.add_suggested_values_to_schema(USER_SCHEMA, suggested),
            errors=errors,
        )

    async def async_step_hassio(
        self, discovery_info: HassioServiceInfo
    ) -> ConfigFlowResult:
        """Handle Supervisor app discovery."""
        _LOGGER.debug("Supervisor discovery info: %s", discovery_info)
        config = discovery_info.config or {}
        install_id = config.get("install_id") or discovery_info.uuid
        await self.async_set_unique_id(str(install_id))
        self._abort_if_unique_id_configured()

        self._hassio_discovery = discovery_info
        self.context.update(
            {
                "title_placeholders": {"name": discovery_info.name},
                "configuration_url": (
                    f"homeassistant://hassio/addon/{discovery_info.slug}/info"
                ),
            }
        )
        return await self.async_step_hassio_confirm()

    async def async_step_hassio_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Confirm Supervisor discovery and validate SUPERVISOR_TOKEN auth."""
        errors: dict[str, str] = {}
        assert self._hassio_discovery is not None
        discovery = self._hassio_discovery

        if user_input is not None:
            config = discovery.config or {}
            host = str(config.get("uri") or "").strip().rstrip("/")
            token = os.environ.get(ENV_SUPERVISOR_TOKEN, "").strip()
            if not host:
                errors["base"] = "cannot_connect"
            elif not token:
                errors["base"] = "invalid_auth"
            else:
                session = async_get_clientsession(self.hass)
                client = SolarAiClient(
                    host=host,
                    access_token=token,
                    verify_ssl=True,
                    session=session,
                )
                try:
                    health = await client.get_health()
                    await client.get_me()
                except ClientResponseError as err:
                    if err.status == 401:
                        errors["base"] = "invalid_auth"
                    else:
                        errors["base"] = "cannot_connect"
                except ClientError:
                    errors["base"] = "cannot_connect"
                except Exception:  # noqa: BLE001
                    _LOGGER.exception("Unexpected error during hassio confirm")
                    errors["base"] = "unknown"
                else:
                    install_id = (
                        config.get("install_id")
                        or health.get("install_id")
                        or discovery.uuid
                    )
                    await self.async_set_unique_id(str(install_id))
                    self._abort_if_unique_id_configured()
                    title = discovery.name or f"Solar AI Optimizer ({str(install_id)[:8]})"
                    return self.async_create_entry(
                        title=title,
                        data={
                            CONF_HOST: host,
                            CONF_VERIFY_SSL: True,
                            CONF_AUTH_MODE: AUTH_MODE_SUPERVISOR,
                            CONF_INSTALL_ID: str(install_id),
                            CONF_CLIENT_ID: "supervisor",
                        },
                    )

        return self.async_show_form(
            step_id="hassio_confirm",
            description_placeholders={"addon": discovery.name},
            errors=errors,
        )

    async def async_step_zeroconf(
        self, discovery_info: ZeroconfServiceInfo
    ) -> ConfigFlowResult:
        """Handle zeroconf discovery — prefill host, continue to pairing."""
        _LOGGER.debug("Zeroconf discovery info: %s", discovery_info)
        props = discovery_info.properties or {}
        uri = (props.get("uri") or props.get("url") or "").strip()
        if uri:
            host = uri.rstrip("/")
        else:
            port = discovery_info.port or DEFAULT_HTTP_PORT
            host = f"http://{discovery_info.host}:{port}"

        install_id = props.get("install_id")
        if install_id:
            await self.async_set_unique_id(str(install_id))
            self._abort_if_unique_id_configured(
                updates={CONF_HOST: host},
            )

        self._discovered_host = host
        self.context["title_placeholders"] = {
            "name": discovery_info.name.split(".")[0]
        }
        return await self.async_step_user()

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Allow changing host / SSL without re-pairing."""
        entry = self._get_reconfigure_entry()
        errors: dict[str, str] = {}

        if user_input is not None:
            host = str(user_input[CONF_HOST]).strip().rstrip("/")
            verify_ssl = bool(user_input.get(CONF_VERIFY_SSL, True))
            access_token, _ = resolve_access_token(entry.data)
            session = async_get_clientsession(self.hass)
            client = SolarAiClient(
                host=host,
                access_token=access_token,
                verify_ssl=verify_ssl,
                session=session,
            )
            try:
                health = await client.get_health()
            except ClientError:
                errors["base"] = "cannot_connect"
            except Exception:  # noqa: BLE001
                _LOGGER.exception("Unexpected error during reconfigure")
                errors["base"] = "unknown"
            else:
                install_id = health.get("install_id") or entry.data.get(CONF_INSTALL_ID)
                if install_id:
                    await self.async_set_unique_id(str(install_id))
                    self._abort_if_unique_id_mismatch(reason="wrong_install")
                return self.async_update_reload_and_abort(
                    entry,
                    data_updates={
                        CONF_HOST: host,
                        CONF_VERIFY_SSL: verify_ssl,
                    },
                )

        return self.async_show_form(
            step_id="reconfigure",
            data_schema=self.add_suggested_values_to_schema(
                RECONFIGURE_SCHEMA,
                {
                    CONF_HOST: entry.data.get(CONF_HOST),
                    CONF_VERIFY_SSL: entry.data.get(CONF_VERIFY_SSL, True),
                },
            ),
            errors=errors,
        )

    async def async_step_reauth(
        self, entry_data: dict[str, Any]
    ) -> ConfigFlowResult:
        """Start reauth when Solar returns 401."""
        _ = entry_data
        self._reauth_entry = self.hass.config_entries.async_get_entry(
            self.context["entry_id"]
        )
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Re-pair with a new pairing code."""
        errors: dict[str, str] = {}
        entry = self._reauth_entry
        if entry is None:
            return self.async_abort(reason="reauth_successful")

        if user_input is not None:
            pair_code = (user_input.get(CONF_PAIR_CODE) or "").strip()
            session = async_get_clientsession(self.hass)
            client = SolarAiClient(
                host=entry.data[CONF_HOST],
                access_token="",
                verify_ssl=entry.data.get(CONF_VERIFY_SSL, True),
                session=session,
            )
            try:
                redeemed = await client.redeem_pair(pair_code)
                token = redeemed["access_token"]
                client_id = redeemed.get("client_id")
                redeemed_install = redeemed.get("install_id")
                auth_client = SolarAiClient(
                    host=entry.data[CONF_HOST],
                    access_token=token,
                    verify_ssl=entry.data.get(CONF_VERIFY_SSL, True),
                    session=session,
                )
                await auth_client.get_me()
            except ClientResponseError as err:
                if err.status in (400, 409):
                    errors["base"] = "invalid_pair_code"
                elif err.status == 401:
                    errors["base"] = "invalid_auth"
                else:
                    errors["base"] = "cannot_connect"
            except ClientError:
                errors["base"] = "cannot_connect"
            except Exception:  # noqa: BLE001
                _LOGGER.exception("Unexpected reauth error")
                errors["base"] = "unknown"
            else:
                expected = entry.data.get(CONF_INSTALL_ID) or entry.unique_id
                if (
                    redeemed_install
                    and expected
                    and str(redeemed_install) != str(expected)
                ):
                    return self.async_abort(reason="wrong_install")
                return self.async_update_reload_and_abort(
                    entry,
                    data_updates={
                        CONF_ACCESS_TOKEN: token,
                        CONF_AUTH_MODE: AUTH_MODE_TOKEN,
                        CONF_CLIENT_ID: client_id,
                    },
                )

        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=REAUTH_SCHEMA,
            errors=errors,
        )


class SolarAiOptionsFlow(OptionsFlowWithReload):
    """Handle options — fail-safe entities and thresholds."""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Manage the options."""
        if user_input is not None:
            switch_id, number_id = failsafe_entity_ids(user_input, {})
            async_check_failsafe_repair(
                self.hass,
                self.config_entry.entry_id,
                switch_id=switch_id,
                number_id=number_id,
            )
            return self.async_create_entry(data=user_input)

        return self.async_show_form(
            step_id="init",
            data_schema=self.add_suggested_values_to_schema(
                OPTIONS_SCHEMA, self.config_entry.options
            ),
        )
