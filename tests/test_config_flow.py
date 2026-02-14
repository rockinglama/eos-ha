"""Tests for EOS HA config flow."""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import aiohttp
import pytest

from homeassistant import config_entries
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from custom_components.eos_ha.const import (
    CONF_BATTERY_CAPACITY,
    CONF_CONSUMPTION_ENTITY,
    CONF_EOS_URL,
    CONF_FEED_IN_TARIFF,
    CONF_INVERTER_POWER,
    CONF_MAX_CHARGE_POWER,
    CONF_MAX_SOC,
    CONF_MIN_SOC,
    CONF_PRICE_SOURCE,
    CONF_SOC_ENTITY,
    DOMAIN,
    PRICE_SOURCE_AKKUDOKTOR,
)


def _mock_aiohttp_response(status=200, json_data=None):
    """Create a mock aiohttp response as async context manager."""
    mock_resp = AsyncMock()
    mock_resp.status = status
    mock_resp.json = AsyncMock(return_value=json_data or {})
    mock_resp.text = AsyncMock(return_value="")

    cm = AsyncMock()
    cm.__aenter__ = AsyncMock(return_value=mock_resp)
    cm.__aexit__ = AsyncMock(return_value=False)
    return cm


async def test_user_step_shows_form(hass: HomeAssistant) -> None:
    """Test that the user step shows a form."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "user"


async def test_user_step_connection_error(hass: HomeAssistant) -> None:
    """Test connection error in user step."""
    hass.config.latitude = 52.52
    hass.config.longitude = 13.405

    with patch(
        "homeassistant.helpers.aiohttp_client.async_get_clientsession",
    ) as mock_session:
        session = MagicMock()
        session.get = MagicMock(side_effect=aiohttp.ClientError("Connection refused"))
        mock_session.return_value = session

        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_EOS_URL: "http://192.168.1.20:8503"},
        )
        assert result["type"] == FlowResultType.FORM
        assert result["errors"]["base"] == "cannot_connect"


async def test_user_step_invalid_response(hass: HomeAssistant) -> None:
    """Test invalid response from EOS server."""
    hass.config.latitude = 52.52
    hass.config.longitude = 13.405

    with patch(
        "homeassistant.helpers.aiohttp_client.async_get_clientsession",
    ) as mock_session:
        session = MagicMock()
        session.get = MagicMock(return_value=_mock_aiohttp_response(500))
        mock_session.return_value = session

        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_EOS_URL: "http://192.168.1.20:8503"},
        )
        assert result["type"] == FlowResultType.FORM
        assert result["errors"]["base"] == "invalid_response"


async def test_full_flow_akkudoktor_price(hass: HomeAssistant) -> None:
    """Test the full config flow with Akkudoktor price source (happy path)."""
    hass.config.latitude = 52.52
    hass.config.longitude = 13.405

    with patch(
        "homeassistant.helpers.aiohttp_client.async_get_clientsession",
    ) as mock_session:
        session = MagicMock()
        session.get = MagicMock(
            return_value=_mock_aiohttp_response(200, {"status": "alive", "version": "0.1.0"})
        )
        mock_session.return_value = session

        # Step 1: User (EOS URL)
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
        assert result["type"] == FlowResultType.FORM
        assert result["step_id"] == "user"

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_EOS_URL: "http://192.168.1.20:8503"},
        )

        # Step 2: Price source
        assert result["type"] == FlowResultType.FORM
        assert result["step_id"] == "price_source"

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_PRICE_SOURCE: PRICE_SOURCE_AKKUDOKTOR},
        )

        # Step 3: Entities (no price — akkudoktor mode)
        assert result["type"] == FlowResultType.FORM
        assert result["step_id"] == "entities_no_price"

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_SOC_ENTITY: "sensor.battery_soc",
                CONF_CONSUMPTION_ENTITY: "sensor.consumption",
            },
        )

        # Step 4: Battery
        assert result["type"] == FlowResultType.FORM
        assert result["step_id"] == "battery"

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_BATTERY_CAPACITY: 10.0,
                CONF_MAX_CHARGE_POWER: 5000,
                CONF_MIN_SOC: 15,
                CONF_MAX_SOC: 90,
                CONF_INVERTER_POWER: 10000,
                CONF_FEED_IN_TARIFF: 0.082,
            },
        )

        # Step 5: Battery sensors (optional)
        assert result["type"] == FlowResultType.FORM
        assert result["step_id"] == "battery_sensors"

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {},
        )

        # Step 6: EV
        assert result["type"] == FlowResultType.FORM
        assert result["step_id"] == "ev"

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                "ev_enabled": False,
                "ev_capacity": 60.0,
                "ev_charge_power": 11000,
                "ev_efficiency": 0.95,
            },
        )

        # Step 7: PV overview — finish immediately
        assert result["type"] == FlowResultType.FORM
        assert result["step_id"] == "pv_overview"

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {"action": "finish"},
        )

        assert result["type"] == FlowResultType.CREATE_ENTRY
        assert result["title"] == "EOS HA"
        assert result["data"][CONF_EOS_URL] == "http://192.168.1.20:8503"


async def test_abort_duplicate(hass: HomeAssistant) -> None:
    """Test that duplicate config entries are aborted."""
    # Create an existing entry
    entry = config_entries.ConfigEntry(
        version=1,
        minor_version=1,
        domain=DOMAIN,
        title="EOS HA",
        data={CONF_EOS_URL: "http://192.168.1.20:8503"},
        source=config_entries.SOURCE_USER,
        unique_id=DOMAIN,
    )
    entry.add_to_hass(hass)

    hass.config.latitude = 52.52
    hass.config.longitude = 13.405

    with patch(
        "homeassistant.helpers.aiohttp_client.async_get_clientsession",
    ) as mock_session:
        session = MagicMock()
        session.get = MagicMock(
            return_value=_mock_aiohttp_response(200, {"status": "alive", "version": "0.1.0"})
        )
        mock_session.return_value = session

        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_EOS_URL: "http://192.168.1.20:8503"},
        )
        assert result["type"] == FlowResultType.ABORT
        assert result["reason"] == "already_configured"


async def test_pv_add_flow(hass: HomeAssistant) -> None:
    """Test adding a PV array during setup."""
    hass.config.latitude = 52.52
    hass.config.longitude = 13.405

    with patch(
        "homeassistant.helpers.aiohttp_client.async_get_clientsession",
    ) as mock_session:
        session = MagicMock()
        session.get = MagicMock(
            return_value=_mock_aiohttp_response(200, {"status": "alive", "version": "0.1.0"})
        )
        mock_session.return_value = session

        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {CONF_EOS_URL: "http://192.168.1.20:8503"},
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {CONF_PRICE_SOURCE: PRICE_SOURCE_AKKUDOKTOR},
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_SOC_ENTITY: "sensor.battery_soc", CONF_CONSUMPTION_ENTITY: "sensor.consumption"},
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_BATTERY_CAPACITY: 10.0, CONF_MAX_CHARGE_POWER: 5000, CONF_MIN_SOC: 15, CONF_MAX_SOC: 90, CONF_INVERTER_POWER: 10000, CONF_FEED_IN_TARIFF: 0.082},
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {},
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {"ev_enabled": False, "ev_capacity": 60.0, "ev_charge_power": 11000, "ev_efficiency": 0.95},
        )

        # PV overview — add an array
        assert result["step_id"] == "pv_overview"
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {"action": "add"},
        )
        assert result["step_id"] == "pv_add"

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {"azimuth": 180, "tilt": 30, "power": 5000, "inverter_power": 5000, "inverter_efficiency": 0.9},
        )

        # Back to overview — finish
        assert result["step_id"] == "pv_overview"
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {"action": "finish"},
        )

        assert result["type"] == FlowResultType.CREATE_ENTRY
        assert len(result["data"]["pv_arrays"]) == 1
        assert result["data"]["pv_arrays"][0]["azimuth"] == 180
