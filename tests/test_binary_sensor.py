"""Tests for EOS HA binary sensor platform."""
from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from custom_components.eos_ha.binary_sensor import (
    EOSDischargeAllowedSensor,
    PARALLEL_UPDATES,
)


def test_parallel_updates():
    """Test PARALLEL_UPDATES is set to 1."""
    assert PARALLEL_UPDATES == 1


def _make_coordinator(data=None):
    """Create a mock coordinator."""
    coord = MagicMock()
    coord.config_entry = MagicMock()
    coord.config_entry.entry_id = "test_entry"
    coord.data = data
    return coord


def test_discharge_allowed_on():
    """Test discharge allowed returns True."""
    coord = _make_coordinator({"discharge_allowed": [1, 0, 1]})
    sensor = EOSDischargeAllowedSensor(coord)
    assert sensor.is_on is True


def test_discharge_allowed_off():
    """Test discharge allowed returns False."""
    coord = _make_coordinator({"discharge_allowed": [0, 1, 1]})
    sensor = EOSDischargeAllowedSensor(coord)
    assert sensor.is_on is False


def test_discharge_allowed_no_data():
    """Test discharge allowed returns None with no data."""
    coord = _make_coordinator(None)
    sensor = EOSDischargeAllowedSensor(coord)
    assert sensor.is_on is None


def test_discharge_allowed_empty_array():
    """Test discharge allowed returns None with empty array."""
    coord = _make_coordinator({"discharge_allowed": []})
    sensor = EOSDischargeAllowedSensor(coord)
    assert sensor.is_on is None


def test_discharge_extra_attrs():
    """Test extra state attributes."""
    data = {"discharge_allowed": [1, 0, 1]}
    coord = _make_coordinator(data)
    sensor = EOSDischargeAllowedSensor(coord)
    assert sensor.extra_state_attributes == {"forecast": [1, 0, 1]}


def test_discharge_extra_attrs_no_data():
    """Test extra state attributes with no data."""
    coord = _make_coordinator(None)
    sensor = EOSDischargeAllowedSensor(coord)
    assert sensor.extra_state_attributes == {}


def test_unique_id():
    """Test unique_id format."""
    coord = _make_coordinator({})
    sensor = EOSDischargeAllowedSensor(coord)
    assert sensor.unique_id == "test_entry_discharge_allowed"
