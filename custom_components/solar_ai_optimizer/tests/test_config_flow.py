"""Config flow tests for Solar AI Optimizer."""

from __future__ import annotations

from unittest.mock import AsyncMock

from aiohttp import ClientError, ClientResponseError
from homeassistant.config_entries import SOURCE_REAUTH, SOURCE_USER
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers import issue_registry as ir
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.solar_ai_optimizer.const import (
    CONF_ACCESS_TOKEN,
    CONF_GRID_CHARGE_ENABLE,
    CONF_HOST,
    CONF_INSTALL_ID,
    CONF_MAX_GRID_CHARGE_CURRENT,
    CONF_PAIR_CODE,
    CONF_VERIFY_SSL,
    DOMAIN,
)
from custom_components.solar_ai_optimizer.repairs import ISSUE_FAILSAFE_INCOMPLETE


def _http_error(status: int) -> ClientResponseError:
    err = ClientResponseError(
        request_info=None,  # type: ignore[arg-type]
        history=(),
        status=status,
        message="err",
    )
    err.__str__ = lambda: f"{status} err"  # type: ignore[method-assign]
    return err


async def test_user_flow_pairing(
    hass: HomeAssistant, mock_client: AsyncMock
) -> None:
    """Test successful user flow with pairing code."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_HOST: "http://192.168.1.10:8000/",
            CONF_VERIFY_SSL: True,
            CONF_PAIR_CODE: "ABCD-1234",
            CONF_GRID_CHARGE_ENABLE: "switch.grid",
            CONF_MAX_GRID_CHARGE_CURRENT: "number.amps",
            "stale_seconds": 90,
            "debounce_seconds": 60,
        },
    )
    assert result2["type"] is FlowResultType.CREATE_ENTRY
    assert result2["data"][CONF_HOST] == "http://192.168.1.10:8000"
    assert result2["data"][CONF_ACCESS_TOKEN] == "sol_c_test_token"
    assert result2["data"][CONF_INSTALL_ID] == "install-abc12345"
    assert result2["options"][CONF_GRID_CHARGE_ENABLE] == "switch.grid"
    mock_client.redeem_pair.assert_awaited()


async def test_user_flow_api_token(
    hass: HomeAssistant, mock_client: AsyncMock
) -> None:
    """Advanced flow: paste API token without pairing."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_HOST: "http://192.168.1.10:8000",
            CONF_ACCESS_TOKEN: "sol_c_pasted",
        },
    )
    assert result2["type"] is FlowResultType.CREATE_ENTRY
    assert result2["data"][CONF_ACCESS_TOKEN] == "sol_c_pasted"
    assert result2["data"]["client_id"] == "api-token"


async def test_user_flow_missing_auth(
    hass: HomeAssistant, mock_client: AsyncMock
) -> None:
    """Neither pair code nor token yields invalid_auth."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_HOST: "http://192.168.1.10:8000"},
    )
    assert result2["type"] is FlowResultType.FORM
    assert result2["errors"]["base"] == "invalid_auth"


async def test_user_flow_cannot_connect(
    hass: HomeAssistant, mock_client: AsyncMock
) -> None:
    """Test cannot_connect error on health probe."""
    mock_client.get_health = AsyncMock(side_effect=ClientError("down"))
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_HOST: "http://192.168.1.10:8000", CONF_PAIR_CODE: "ABCD-1234"},
    )
    assert result2["type"] is FlowResultType.FORM
    assert result2["errors"]["base"] == "cannot_connect"


async def test_user_flow_unknown_health(
    hass: HomeAssistant, mock_client: AsyncMock
) -> None:
    """Non-ClientError health failure becomes unknown."""
    mock_client.get_health = AsyncMock(side_effect=RuntimeError("boom"))
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_HOST: "http://192.168.1.10:8000", CONF_PAIR_CODE: "ABCD-1234"},
    )
    assert result2["errors"]["base"] == "unknown"


async def test_user_flow_pair_errors(
    hass: HomeAssistant, mock_client: AsyncMock
) -> None:
    """Pair redeem maps HTTP statuses and network errors."""
    cases = [
        (_http_error(400), "invalid_pair_code"),
        (_http_error(409), "invalid_pair_code"),
        (_http_error(401), "invalid_auth"),
        (_http_error(500), "cannot_connect"),
        (ClientError("net"), "cannot_connect"),
    ]
    for side_effect, expected in cases:
        mock_client.redeem_pair = AsyncMock(side_effect=side_effect)
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_USER}
        )
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_HOST: "http://192.168.1.10:8000", CONF_PAIR_CODE: "BAD"},
        )
        assert result2["errors"]["base"] == expected, expected


async def test_user_flow_missing_install_id(
    hass: HomeAssistant, mock_client: AsyncMock
) -> None:
    """Token without install_id surfaces unknown."""
    mock_client.get_health = AsyncMock(return_value={"version": "1.0.0"})
    mock_client.redeem_pair = AsyncMock(
        return_value={"access_token": "tok", "client_id": "c"}
    )
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_HOST: "http://192.168.1.10:8000", CONF_PAIR_CODE: "ABCD-1234"},
    )
    assert result2["type"] is FlowResultType.FORM
    assert result2["errors"]["base"] == "unknown"


async def test_user_flow_duplicate(
    hass: HomeAssistant, mock_client: AsyncMock, mock_config_entry: MockConfigEntry
) -> None:
    """Test abort when install already configured."""
    mock_config_entry.add_to_hass(hass)
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_HOST: "http://192.168.1.10:8000", CONF_PAIR_CODE: "ABCD-1234"},
    )
    assert result2["type"] is FlowResultType.ABORT
    assert result2["reason"] == "already_configured"


async def test_reauth_flow(
    hass: HomeAssistant, mock_client: AsyncMock, mock_config_entry: MockConfigEntry
) -> None:
    """Test reauth with a new pairing code."""
    mock_config_entry.add_to_hass(hass)
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={
            "source": SOURCE_REAUTH,
            "entry_id": mock_config_entry.entry_id,
            "unique_id": mock_config_entry.unique_id,
        },
        data=mock_config_entry.data,
    )
    assert result["type"] is FlowResultType.FORM
    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_PAIR_CODE: "NEW1-CODE"}
    )
    assert result2["type"] is FlowResultType.ABORT
    assert result2["reason"] == "reauth_successful"
    await hass.async_block_till_done()


async def test_reauth_wrong_install(
    hass: HomeAssistant, mock_client: AsyncMock, mock_config_entry: MockConfigEntry
) -> None:
    """Reauth aborts when redeem returns a different install."""
    mock_config_entry.add_to_hass(hass)
    mock_client.redeem_pair = AsyncMock(
        return_value={
            "access_token": "tok",
            "client_id": "c",
            "install_id": "other-install",
        }
    )
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={
            "source": SOURCE_REAUTH,
            "entry_id": mock_config_entry.entry_id,
            "unique_id": mock_config_entry.unique_id,
        },
        data=mock_config_entry.data,
    )
    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_PAIR_CODE: "NEW1-CODE"}
    )
    assert result2["type"] is FlowResultType.ABORT
    assert result2["reason"] == "wrong_install"


async def test_reauth_errors(
    hass: HomeAssistant, mock_client: AsyncMock, mock_config_entry: MockConfigEntry
) -> None:
    """Reauth maps pair and network failures."""
    mock_config_entry.add_to_hass(hass)
    cases = [
        (_http_error(400), "invalid_pair_code"),
        (_http_error(500), "cannot_connect"),
        (ClientError("x"), "cannot_connect"),
        (RuntimeError("x"), "unknown"),
    ]
    for side_effect, expected in cases:
        mock_client.redeem_pair = AsyncMock(side_effect=side_effect)
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={
                "source": SOURCE_REAUTH,
                "entry_id": mock_config_entry.entry_id,
                "unique_id": mock_config_entry.unique_id,
            },
            data=mock_config_entry.data,
        )
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"], {CONF_PAIR_CODE: "X"}
        )
        assert result2["errors"]["base"] == expected


async def test_reauth_missing_entry(hass: HomeAssistant) -> None:
    """Reauth confirm without entry aborts successfully."""
    from custom_components.solar_ai_optimizer.config_flow import SolarAiConfigFlow

    flow = SolarAiConfigFlow()
    flow.hass = hass
    flow._reauth_entry = None
    result = await flow.async_step_reauth_confirm({CONF_PAIR_CODE: "X"})
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"


async def test_reconfigure_flow(
    hass: HomeAssistant, mock_client: AsyncMock, mock_config_entry: MockConfigEntry
) -> None:
    """Test reconfigure updates host while keeping token."""
    mock_config_entry.add_to_hass(hass)
    result = await mock_config_entry.start_reconfigure_flow(hass)
    assert result["type"] is FlowResultType.FORM
    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_HOST: "http://192.168.1.20:8000", CONF_VERIFY_SSL: False},
    )
    assert result2["type"] is FlowResultType.ABORT
    assert result2["reason"] == "reconfigure_successful"
    assert mock_config_entry.data[CONF_HOST] == "http://192.168.1.20:8000"
    assert mock_config_entry.data[CONF_VERIFY_SSL] is False
    assert mock_config_entry.data[CONF_ACCESS_TOKEN] == "sol_c_test_token"
    await hass.async_block_till_done()


async def test_reconfigure_errors(
    hass: HomeAssistant, mock_client: AsyncMock, mock_config_entry: MockConfigEntry
) -> None:
    """Reconfigure maps connection and unexpected errors."""
    mock_config_entry.add_to_hass(hass)

    mock_client.get_health = AsyncMock(side_effect=ClientError("down"))
    result = await mock_config_entry.start_reconfigure_flow(hass)
    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_HOST: "http://bad:8000", CONF_VERIFY_SSL: True},
    )
    assert result2["errors"]["base"] == "cannot_connect"

    mock_client.get_health = AsyncMock(side_effect=RuntimeError("x"))
    result = await mock_config_entry.start_reconfigure_flow(hass)
    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_HOST: "http://bad:8000", CONF_VERIFY_SSL: True},
    )
    assert result2["errors"]["base"] == "unknown"


async def test_reconfigure_wrong_install(
    hass: HomeAssistant, mock_client: AsyncMock, mock_config_entry: MockConfigEntry
) -> None:
    """Reconfigure aborts when host belongs to another install."""
    mock_config_entry.add_to_hass(hass)
    mock_client.get_health = AsyncMock(
        return_value={"install_id": "completely-different"}
    )
    result = await mock_config_entry.start_reconfigure_flow(hass)
    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_HOST: "http://other:8000", CONF_VERIFY_SSL: True},
    )
    assert result2["type"] is FlowResultType.ABORT
    assert result2["reason"] == "wrong_install"


async def test_options_flow(
    hass: HomeAssistant, mock_client: AsyncMock, mock_config_entry: MockConfigEntry
) -> None:
    """Test options flow stores fail-safe thresholds."""
    mock_config_entry.add_to_hass(hass)
    result = await hass.config_entries.options.async_init(mock_config_entry.entry_id)
    assert result["type"] is FlowResultType.FORM
    result2 = await hass.config_entries.options.async_configure(
        result["flow_id"],
        {"stale_seconds": 90, "debounce_seconds": 60},
    )
    assert result2["type"] is FlowResultType.CREATE_ENTRY
    assert mock_config_entry.options["stale_seconds"] == 90
    await hass.async_block_till_done()


async def test_options_flow_failsafe_repair(
    hass: HomeAssistant, mock_client: AsyncMock, mock_config_entry: MockConfigEntry
) -> None:
    """Options XOR creates a repair issue."""
    mock_config_entry.add_to_hass(hass)
    result = await hass.config_entries.options.async_init(mock_config_entry.entry_id)
    await hass.config_entries.options.async_configure(
        result["flow_id"],
        {CONF_GRID_CHARGE_ENABLE: "switch.only"},
    )
    issues = ir.async_get(hass)
    assert (
        issues.async_get_issue(
            DOMAIN, f"{ISSUE_FAILSAFE_INCOMPLETE}_{mock_config_entry.entry_id}"
        )
        is not None
    )
    await hass.async_block_till_done()
