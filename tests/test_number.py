"""Tests for EOS HA number platform."""
from custom_components.eos_ha.number import (
    NUMBERS,
    EV_NUMBERS,
    EOSNumber,
    _DEFAULTS,
)
from custom_components.eos_ha.const import (
    CONF_BATTERY_CAPACITY,
    CONF_MAX_SOC,
    CONF_MIN_SOC,
    DEFAULT_BATTERY_CAPACITY,
    DEFAULT_MAX_SOC,
    DEFAULT_MIN_SOC,
)


class TestNumberDescriptions:
    def test_number_keys(self):
        keys = [d.key for d in NUMBERS]
        assert "battery_capacity" in keys
        assert "max_charge_power" in keys
        assert "inverter_power" in keys
        assert "min_soc" in keys
        assert "max_soc" in keys

    def test_ev_number_keys(self):
        keys = [d.key for d in EV_NUMBERS]
        assert "ev_capacity" in keys
        assert "ev_charge_power" in keys

    def test_defaults_mapping(self):
        assert _DEFAULTS[CONF_BATTERY_CAPACITY] == DEFAULT_BATTERY_CAPACITY
        assert _DEFAULTS[CONF_MIN_SOC] == DEFAULT_MIN_SOC
        assert _DEFAULTS[CONF_MAX_SOC] == DEFAULT_MAX_SOC


class TestEOSNumber:
    def test_native_value_from_data(self, mock_coordinator):
        desc = next(d for d in NUMBERS if d.key == "battery_capacity")
        entity = EOSNumber(mock_coordinator, mock_coordinator.config_entry, desc)
        assert entity.native_value == 10.0

    def test_native_value_from_options(self, mock_coordinator):
        mock_coordinator.config_entry.options = {"battery_capacity": 20.0}
        desc = next(d for d in NUMBERS if d.key == "battery_capacity")
        entity = EOSNumber(mock_coordinator, mock_coordinator.config_entry, desc)
        assert entity.native_value == 20.0

    def test_unique_id(self, mock_coordinator):
        desc = next(d for d in NUMBERS if d.key == "min_soc")
        entity = EOSNumber(mock_coordinator, mock_coordinator.config_entry, desc)
        assert entity.unique_id == "test_entry_id_min_soc"
