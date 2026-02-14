"""Tests for EOS HA coordinator."""
from __future__ import annotations

from datetime import timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import aiohttp
import pytest

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import UpdateFailed
from homeassistant.util import dt as dt_util

from custom_components.eos_ha.coordinator import EOSCoordinator
from custom_components.eos_ha.api import EOSConnectionError, EOSOptimizationError


MOCK_CONFIG_DATA = {
    "eos_url": "http://localhost:8503",
    "soc_entity": "sensor.battery_soc",
    "consumption_entity": "sensor.consumption",
    "battery_capacity": 10.0,
    "max_charge_power": 5000,
    "min_soc": 15,
    "max_soc": 90,
    "inverter_power": 10000,
    "price_source": "akkudoktor",
    "feed_in_tariff": 0.082,
    "latitude": 52.0,
    "longitude": 13.0,
    "pv_arrays": [],
}


@pytest.fixture
def mock_config_entry():
    """Create a mock config entry."""
    entry = MagicMock()
    entry.data = MOCK_CONFIG_DATA.copy()
    entry.options = {}
    entry.entry_id = "test_entry_id"
    return entry


@pytest.fixture
def mock_session():
    """Create a mock aiohttp session."""
    session = MagicMock(spec=aiohttp.ClientSession)
    session.close = AsyncMock()
    return session


@pytest.fixture
def coordinator(hass: HomeAssistant, mock_config_entry, mock_session):
    """Create an EOSCoordinator with mocked dependencies."""
    with patch("custom_components.eos_ha.coordinator.aiohttp.ClientSession", return_value=mock_session):
        coord = EOSCoordinator(hass, mock_config_entry)
    return coord


async def test_first_refresh_returns_empty_data(hass: HomeAssistant, coordinator):
    """Test that first refresh returns empty data and configures EOS."""
    assert coordinator._first_refresh is True

    with patch.object(coordinator, "_push_eos_config", new_callable=AsyncMock):
        result = await coordinator._async_update_data()

    assert coordinator._first_refresh is False
    assert result["last_success"] is False
    assert result["ac_charge"] == []


async def test_empty_data_structure(coordinator):
    """Test empty data has all required keys."""
    data = coordinator._empty_data()
    assert "ac_charge" in data
    assert "dc_charge" in data
    assert "discharge_allowed" in data
    assert "last_update" in data
    assert data["last_success"] is False


async def test_set_override(coordinator):
    """Test setting and clearing override."""
    coordinator.set_override("charge", 60)
    assert coordinator.active_override == "charge"

    coordinator.set_override("auto", 0)
    assert coordinator.active_override is None


async def test_override_expires(coordinator):
    """Test that override expires after duration."""
    coordinator.set_override("charge", 60)
    assert coordinator.active_override == "charge"

    # Manually expire it
    coordinator._override_until = dt_util.now() - timedelta(minutes=1)
    assert coordinator.active_override is None


async def test_get_config_fallback(coordinator):
    """Test _get_config falls back from options to data."""
    assert coordinator._get_config("battery_capacity") == 10.0
    assert coordinator._get_config("nonexistent", "default") == "default"


async def test_eos_client_property(coordinator):
    """Test eos_client property returns the API client."""
    assert coordinator.eos_client is not None


async def test_async_shutdown(coordinator, mock_session):
    """Test shutdown closes the session."""
    await coordinator.async_shutdown()
    mock_session.close.assert_called_once()


async def test_log_when_unavailable(hass: HomeAssistant, coordinator, caplog):
    """Test that unavailability is logged once, and recovery is logged once."""
    coordinator._first_refresh = False
    coordinator._eos_configured = True

    # Set up HA states
    hass.states.async_set("sensor.battery_soc", "50")
    hass.states.async_set("sensor.consumption", "500")

    # Mock the optimization to fail
    with patch.object(
        coordinator._eos_client, "optimize",
        side_effect=EOSConnectionError("Connection refused"),
    ), patch.object(coordinator, "_push_measurements", new_callable=AsyncMock), \
         patch.object(coordinator, "_push_load_history", new_callable=AsyncMock), \
         patch.object(coordinator._eos_client, "get_energy_plan", new_callable=AsyncMock, return_value={}), \
         patch.object(coordinator._eos_client, "get_resource_status", new_callable=AsyncMock, return_value={}), \
         patch.object(coordinator._eos_client, "get_pvforecast", new_callable=AsyncMock, return_value=[0.0] * 48), \
         patch.object(coordinator._eos_client, "get_strompreis", new_callable=AsyncMock, return_value=[0.0001] * 48):

        with pytest.raises(UpdateFailed):
            await coordinator._async_update_data()

    assert coordinator._last_available is False
    assert "EOS server is unavailable" in caplog.text

    # Second failure should NOT log again
    caplog.clear()
    with patch.object(
        coordinator._eos_client, "optimize",
        side_effect=EOSConnectionError("Connection refused"),
    ), patch.object(coordinator, "_push_measurements", new_callable=AsyncMock), \
         patch.object(coordinator, "_push_load_history", new_callable=AsyncMock), \
         patch.object(coordinator._eos_client, "get_energy_plan", new_callable=AsyncMock, return_value={}), \
         patch.object(coordinator._eos_client, "get_resource_status", new_callable=AsyncMock, return_value={}), \
         patch.object(coordinator._eos_client, "get_pvforecast", new_callable=AsyncMock, return_value=[0.0] * 48), \
         patch.object(coordinator._eos_client, "get_strompreis", new_callable=AsyncMock, return_value=[0.0001] * 48):

        with pytest.raises(UpdateFailed):
            await coordinator._async_update_data()

    assert "EOS server is unavailable" not in caplog.text


async def test_log_when_recovered(hass: HomeAssistant, coordinator, caplog):
    """Test that recovery after unavailability is logged."""
    coordinator._first_refresh = False
    coordinator._eos_configured = True
    coordinator._last_available = False  # Was previously unavailable

    hass.states.async_set("sensor.battery_soc", "50")
    hass.states.async_set("sensor.consumption", "500")

    mock_result = {
        "ac_charge": [0.0] * 48,
        "dc_charge": [0.0] * 48,
        "discharge_allowed": [1] * 48,
        "start_solution": None,
        "result": {},
    }

    with patch.object(coordinator._eos_client, "optimize", new_callable=AsyncMock, return_value=mock_result), \
         patch.object(coordinator, "_push_measurements", new_callable=AsyncMock), \
         patch.object(coordinator, "_push_load_history", new_callable=AsyncMock), \
         patch.object(coordinator._eos_client, "get_energy_plan", new_callable=AsyncMock, return_value={}), \
         patch.object(coordinator._eos_client, "get_resource_status", new_callable=AsyncMock, return_value={}), \
         patch.object(coordinator._eos_client, "get_pvforecast", new_callable=AsyncMock, return_value=[0.0] * 48), \
         patch.object(coordinator._eos_client, "get_strompreis", new_callable=AsyncMock, return_value=[0.0001] * 48):

        result = await coordinator._async_update_data()

    assert coordinator._last_available is True
    assert "EOS server connection restored" in caplog.text


async def test_parse_optimization_response(coordinator):
    """Test parsing a valid optimization response."""
    response = {
        "ac_charge": [100.0] * 48,
        "dc_charge": [200.0] * 48,
        "discharge_allowed": [1] * 48,
        "start_solution": "optimal",
        "result": {
            "akku_soc_pro_stunde": [50.0] * 48,
            "Kosten_Euro_pro_Stunde": [0.1] * 48,
            "Gesamtbilanz_Euro": -1.5,
            "Gesamtkosten_Euro": 2.0,
            "Gesamteinnahmen_Euro": 0.5,
        },
    }
    result = coordinator._parse_optimization_response(response)
    assert result["ac_charge"] == [100.0] * 48
    assert result["total_cost"] == 2.0
    assert result["last_success"] is True


async def test_parse_optimization_response_error(coordinator):
    """Test parsing response with error raises UpdateFailed."""
    with pytest.raises(UpdateFailed, match="optimization error"):
        coordinator._parse_optimization_response({"error": "something broke"})


async def test_parse_optimization_response_missing_keys(coordinator):
    """Test parsing response with missing required keys."""
    with pytest.raises(UpdateFailed, match="missing"):
        coordinator._parse_optimization_response({"ac_charge": []})


async def test_extract_consumption_forecast(coordinator):
    """Test consumption forecast extraction."""
    mock_state = MagicMock()
    mock_state.state = "750.5"
    result = coordinator._extract_consumption_forecast(mock_state)
    assert result == [750.5] * 48


async def test_extract_consumption_forecast_invalid(coordinator):
    """Test consumption forecast with invalid state."""
    mock_state = MagicMock()
    mock_state.state = "unavailable"
    result = coordinator._extract_consumption_forecast(mock_state)
    assert result == [500.0] * 48


async def test_build_ev_params_disabled(coordinator):
    """Test EV params returns None when disabled."""
    result = coordinator._build_ev_params(MagicMock())
    assert result is None


async def test_build_ev_params_enabled(coordinator):
    """Test EV params when enabled."""
    coordinator.config_entry.options = {"ev_enabled": True}
    mock_soc = MagicMock()
    mock_soc.state = "50"
    result = coordinator._build_ev_params(mock_soc)
    assert result is not None
    assert result["device_id"] == "ev1"


async def test_build_appliances_empty(coordinator):
    """Test appliances returns None when empty."""
    result = coordinator._build_appliances_params()
    assert result is None
