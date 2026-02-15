"""Fixtures for EOS HA tests."""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest


@pytest.fixture
def mock_coordinator():
    """Create a mock EOSCoordinator."""
    coordinator = MagicMock()
    coordinator.config_entry = MagicMock()
    coordinator.config_entry.entry_id = "test_entry_id"
    coordinator.config_entry.data = {
        "eos_url": "http://localhost:8503",
        "price_source": "akkudoktor",
        "soc_entity": "sensor.battery_soc",
        "battery_capacity": 10.0,
        "max_charge_power": 5000,
        "min_soc": 15,
        "max_soc": 90,
        "inverter_power": 10000,
        "feed_in_tariff": 0.082,
        "yearly_consumption": 12000,
        "pv_arrays": [],
        "ev_enabled": False,
    }
    coordinator.config_entry.options = {}
    coordinator.last_update_success = True
    coordinator.last_exception = None
    coordinator.sg_ready_override = None
    coordinator.data = {
        "ac_charge": [0.5],
        "dc_charge": [0.3],
        "discharge_allowed": [True],
        "pv_forecast": [3000],
        "price_forecast": [0.0003],  # EUR/Wh
        "battery_soc_forecast": [75.0],
        "consumption_forecast": [500],
        "active_override": None,
        "total_cost": 1.23,
        "last_update": "2025-01-01T12:00:00",
        "last_success": True,
        "eos_entities_available": True,
    }
    coordinator.async_request_refresh = AsyncMock()
    return coordinator


@pytest.fixture
def mock_config_data():
    """Return a valid config data dict for config flow tests."""
    return {
        "eos_url": "http://localhost:8503",
        "latitude": 52.52,
        "longitude": 13.405,
        "eos_version": "0.1.0",
        "price_source": "akkudoktor",
        "soc_entity": "sensor.battery_soc",
        "battery_capacity": 10.0,
        "max_charge_power": 5000,
        "min_soc": 15,
        "max_soc": 90,
        "inverter_power": 10000,
        "feed_in_tariff": 0.082,
        "yearly_consumption": 12000,
        "pv_arrays": [],
        "ev_enabled": False,
    }
