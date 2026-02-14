"""Tests for EOS HA sensor platform."""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from homeassistant.core import HomeAssistant

from custom_components.eos_ha.sensor import (
    PARALLEL_UPDATES,
    EOSSensor,
    EOSOptimizationStatusSensor,
    SENSOR_DESCRIPTIONS,
    _current_hour_value,
    _derive_mode,
)


def test_parallel_updates():
    """Test PARALLEL_UPDATES is set to 1."""
    assert PARALLEL_UPDATES == 1


def test_current_hour_value():
    """Test _current_hour_value helper."""
    data = {"ac_charge": [1.234, 2.0, 3.0]}
    assert _current_hour_value(data, "ac_charge") == 1.23

    # Empty array
    assert _current_hour_value(data, "missing") is None
    assert _current_hour_value({"ac_charge": []}, "ac_charge") is None


def test_derive_mode_grid_charge():
    """Test mode derivation for grid charging."""
    data = {"ac_charge": [100.0], "discharge_allowed": [1], "active_override": None}
    assert _derive_mode(data) == "Grid Charge"


def test_derive_mode_avoid_discharge():
    """Test mode derivation for avoid discharge."""
    data = {"ac_charge": [0], "discharge_allowed": [0], "active_override": None}
    assert _derive_mode(data) == "Avoid Discharge"


def test_derive_mode_allow_discharge():
    """Test mode derivation for allow discharge."""
    data = {"ac_charge": [0], "discharge_allowed": [1], "active_override": None}
    assert _derive_mode(data) == "Allow Discharge"


def test_derive_mode_override_charge():
    """Test mode derivation with charge override."""
    data = {"ac_charge": [0], "discharge_allowed": [1], "active_override": "charge"}
    assert _derive_mode(data) == "Override: Charge"


def test_derive_mode_override_discharge():
    """Test mode derivation with discharge override."""
    data = {"ac_charge": [0], "discharge_allowed": [1], "active_override": "discharge"}
    assert _derive_mode(data) == "Override: Discharge"


def _make_coordinator(data=None):
    """Create a mock coordinator."""
    coord = MagicMock()
    coord.config_entry = MagicMock()
    coord.config_entry.entry_id = "test_entry"
    coord.config_entry.data = {"eos_url": "http://localhost:8503"}
    coord.data = data
    coord.last_update_success = True
    return coord


def test_eos_sensor_native_value():
    """Test EOSSensor returns correct native_value."""
    data = {"ac_charge": [42.567] + [0.0] * 47}
    coord = _make_coordinator(data)
    desc = SENSOR_DESCRIPTIONS[0]  # ac_charge_power
    sensor = EOSSensor(coord, desc)
    assert sensor.native_value == 42.57


def test_eos_sensor_no_data():
    """Test EOSSensor returns None when no data."""
    coord = _make_coordinator(None)
    desc = SENSOR_DESCRIPTIONS[0]
    sensor = EOSSensor(coord, desc)
    assert sensor.native_value is None


def test_eos_sensor_extra_attributes():
    """Test EOSSensor extra_state_attributes."""
    data = {"ac_charge": [1.0] * 48}
    coord = _make_coordinator(data)
    desc = SENSOR_DESCRIPTIONS[0]  # has attrs_fn
    sensor = EOSSensor(coord, desc)
    attrs = sensor.extra_state_attributes
    assert "forecast" in attrs


def test_eos_sensor_no_attrs_fn():
    """Test EOSSensor without attrs_fn returns None."""
    coord = _make_coordinator({"ac_charge": [0.0] * 48, "discharge_allowed": [1], "active_override": None})
    # current_mode has no attrs_fn
    desc = SENSOR_DESCRIPTIONS[2]
    sensor = EOSSensor(coord, desc)
    assert sensor.extra_state_attributes is None


def test_optimization_status_sensor_optimized():
    """Test optimization status sensor shows optimized."""
    coord = _make_coordinator({"last_success": True, "last_update": "2024-01-01"})
    sensor = EOSOptimizationStatusSensor(coord)
    assert sensor.native_value == "optimized"


def test_optimization_status_sensor_failed():
    """Test optimization status sensor shows failed."""
    coord = _make_coordinator(None)
    coord.last_update_success = False
    sensor = EOSOptimizationStatusSensor(coord)
    assert sensor.native_value == "failed"


def test_optimization_status_sensor_unknown():
    """Test optimization status sensor shows unknown."""
    coord = _make_coordinator(None)
    coord.last_update_success = True
    sensor = EOSOptimizationStatusSensor(coord)
    assert sensor.native_value == "unknown"


def test_optimization_status_attrs():
    """Test optimization status extra attributes."""
    coord = _make_coordinator({"last_success": True, "last_update": "2024-01-01"})
    sensor = EOSOptimizationStatusSensor(coord)
    attrs = sensor.extra_state_attributes
    assert "eos_server_url" in attrs
    assert attrs["last_success"] is True


def test_sensor_unique_id():
    """Test sensor unique_id format."""
    coord = _make_coordinator({})
    desc = SENSOR_DESCRIPTIONS[0]
    sensor = EOSSensor(coord, desc)
    assert sensor.unique_id == "test_entry_ac_charge_power"


def test_sensor_descriptions_count():
    """Test that we have the expected number of sensor descriptions."""
    assert len(SENSOR_DESCRIPTIONS) >= 10
