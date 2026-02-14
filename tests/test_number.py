"""Tests for EOS HA number platform."""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from custom_components.eos_ha.number import (
    EOSNumber,
    NUMBERS,
    EV_NUMBERS,
    PARALLEL_UPDATES,
    _DEFAULTS,
)
from custom_components.eos_ha.const import (
    CONF_BATTERY_CAPACITY,
    CONF_MIN_SOC,
    DEFAULT_BATTERY_CAPACITY,
    DEFAULT_MIN_SOC,
)


def test_parallel_updates():
    """Test PARALLEL_UPDATES is set to 1."""
    assert PARALLEL_UPDATES == 1


def _make_mocks():
    """Create mock coordinator and entry."""
    coord = MagicMock()
    coord.config_entry = MagicMock()
    coord.config_entry.entry_id = "test_entry"
    coord.async_request_refresh = AsyncMock()

    entry = MagicMock()
    entry.entry_id = "test_entry"
    entry.data = {"battery_capacity": 10.0, "min_soc": 15}
    entry.options = {}
    return coord, entry


def test_number_native_value_from_data():
    """Test number entity reads from config data."""
    coord, entry = _make_mocks()
    desc = NUMBERS[0]  # battery_capacity
    number = EOSNumber(coord, entry, desc)
    assert number.native_value == 10.0


def test_number_native_value_from_options():
    """Test number entity prefers options over data."""
    coord, entry = _make_mocks()
    entry.options = {"battery_capacity": 15.0}
    desc = NUMBERS[0]
    number = EOSNumber(coord, entry, desc)
    assert number.native_value == 15.0


def test_number_native_value_default():
    """Test number entity falls back to defaults."""
    coord, entry = _make_mocks()
    entry.data = {}
    desc = NUMBERS[0]
    number = EOSNumber(coord, entry, desc)
    assert number.native_value == DEFAULT_BATTERY_CAPACITY


def test_number_unique_id():
    """Test number entity unique_id."""
    coord, entry = _make_mocks()
    desc = NUMBERS[0]
    number = EOSNumber(coord, entry, desc)
    assert number.unique_id == "test_entry_battery_capacity"


def test_number_descriptions_count():
    """Test we have battery number descriptions."""
    assert len(NUMBERS) == 5
    assert len(EV_NUMBERS) == 2


def test_defaults_dict():
    """Test defaults dict has entries for all config keys."""
    for desc in NUMBERS:
        assert desc.config_key in _DEFAULTS
    for desc in EV_NUMBERS:
        assert desc.config_key in _DEFAULTS


async def test_number_set_value(hass):
    """Test setting a number value updates options."""
    coord, entry = _make_mocks()
    desc = NUMBERS[0]
    number = EOSNumber(coord, entry, desc)
    number.hass = hass

    with patch.object(hass.config_entries, "async_update_entry") as mock_update:
        await number.async_set_native_value(20.0)
        mock_update.assert_called_once()
        call_kwargs = mock_update.call_args
        assert call_kwargs[1]["options"]["battery_capacity"] == 20.0

    coord.async_request_refresh.assert_called_once()
