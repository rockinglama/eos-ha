"""Tests for EOS HA __init__.py — setup, unload, services."""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from homeassistant.core import HomeAssistant
from homeassistant.config_entries import ConfigEntryState
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError

from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.eos_ha.const import DOMAIN


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
    "latitude": 52.0,
    "longitude": 13.0,
}

MOCK_OPTIMIZATION_RESPONSE = {
    "ac_charge": [0.0] * 48,
    "dc_charge": [0.0] * 48,
    "discharge_allowed": [1] * 48,
    "start_solution": None,
    "result": {},
}


@pytest.fixture
def mock_coordinator():
    """Create a mock coordinator."""
    with patch(
        "custom_components.eos_ha.coordinator.EOSCoordinator"
    ) as mock_cls:
        coordinator = mock_cls.return_value
        coordinator.async_config_entry_first_refresh = AsyncMock()
        coordinator.async_request_refresh = AsyncMock()
        coordinator.async_shutdown = AsyncMock()
        coordinator.data = {
            "ac_charge": [0.0] * 48,
            "dc_charge": [0.0] * 48,
            "discharge_allowed": [1] * 48,
            "last_success": True,
            "last_update": "2024-01-01T00:00:00",
        }
        coordinator.last_update_success = True
        coordinator.config_entry = None
        coordinator.eos_client = MagicMock()
        coordinator.eos_client.update_predictions = AsyncMock(return_value=True)
        coordinator.set_override = MagicMock()
        yield coordinator


@pytest.fixture
async def mock_config_entry(hass: HomeAssistant):
    """Create a mock config entry."""
    from homeassistant.core import callback
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="EOS HA",
        data=MOCK_CONFIG_DATA,
        options={},
        unique_id=f"{DOMAIN}_http://localhost:8503",
    )
    entry.add_to_hass(hass)
    return entry


async def test_setup_entry(hass: HomeAssistant, mock_coordinator, mock_config_entry):
    """Test successful setup of config entry."""
    with patch(
        "custom_components.eos_ha.EOSCoordinator", return_value=mock_coordinator
    ):
        result = await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    assert result
    assert mock_config_entry.state == ConfigEntryState.LOADED


async def test_unload_entry(hass: HomeAssistant, mock_coordinator, mock_config_entry):
    """Test unloading a config entry."""
    with patch(
        "custom_components.eos_ha.EOSCoordinator", return_value=mock_coordinator
    ):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

        result = await hass.config_entries.async_unload(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    assert result
    assert mock_config_entry.state == ConfigEntryState.NOT_LOADED
    mock_coordinator.async_shutdown.assert_called_once()


async def test_service_optimize_now(hass: HomeAssistant, mock_coordinator, mock_config_entry):
    """Test optimize_now service."""
    with patch(
        "custom_components.eos_ha.EOSCoordinator", return_value=mock_coordinator
    ):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    assert hass.services.has_service(DOMAIN, "optimize_now")
    await hass.services.async_call(DOMAIN, "optimize_now", blocking=True)
    mock_coordinator.async_request_refresh.assert_called()


async def test_service_set_override(hass: HomeAssistant, mock_coordinator, mock_config_entry):
    """Test set_override service."""
    with patch(
        "custom_components.eos_ha.EOSCoordinator", return_value=mock_coordinator
    ):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    assert hass.services.has_service(DOMAIN, "set_override")
    await hass.services.async_call(
        DOMAIN, "set_override", {"mode": "charge", "duration": 120}, blocking=True
    )
    mock_coordinator.set_override.assert_called_with("charge", 120)


async def test_service_update_predictions(hass: HomeAssistant, mock_coordinator, mock_config_entry):
    """Test update_predictions service."""
    with patch(
        "custom_components.eos_ha.EOSCoordinator", return_value=mock_coordinator
    ):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    assert hass.services.has_service(DOMAIN, "update_predictions")
    await hass.services.async_call(DOMAIN, "update_predictions", blocking=True)
    mock_coordinator.eos_client.update_predictions.assert_called_once_with(force_update=True)


async def test_service_update_predictions_failure(hass: HomeAssistant, mock_coordinator, mock_config_entry):
    """Test update_predictions service when prediction update fails."""
    mock_coordinator.eos_client.update_predictions = AsyncMock(return_value=False)

    with patch(
        "custom_components.eos_ha.EOSCoordinator", return_value=mock_coordinator
    ):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    with pytest.raises(HomeAssistantError, match="failure"):
        await hass.services.async_call(DOMAIN, "update_predictions", blocking=True)


async def test_services_removed_on_last_unload(hass: HomeAssistant, mock_coordinator, mock_config_entry):
    """Test that services are removed when the last entry is unloaded."""
    with patch(
        "custom_components.eos_ha.EOSCoordinator", return_value=mock_coordinator
    ):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()
        assert hass.services.has_service(DOMAIN, "optimize_now")

        await hass.config_entries.async_unload(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    assert not hass.services.has_service(DOMAIN, "optimize_now")
    assert not hass.services.has_service(DOMAIN, "set_override")
    assert not hass.services.has_service(DOMAIN, "update_predictions")
