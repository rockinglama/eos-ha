"""Tests for EOS HA coordinator."""
from custom_components.eos_ha.coordinator import EOSCoordinator, _read_eos_entity

from unittest.mock import MagicMock


class TestReadEosEntity:
    def test_reads_numeric_value(self):
        hass = MagicMock()
        state = MagicMock()
        state.state = "42.5"
        hass.states.get.return_value = state
        assert _read_eos_entity(hass, "sensor.test") == 42.5

    def test_unavailable(self):
        hass = MagicMock()
        state = MagicMock()
        state.state = "unavailable"
        hass.states.get.return_value = state
        assert _read_eos_entity(hass, "sensor.test") is None

    def test_unknown(self):
        hass = MagicMock()
        state = MagicMock()
        state.state = "unknown"
        hass.states.get.return_value = state
        assert _read_eos_entity(hass, "sensor.test") is None

    def test_missing_entity(self):
        hass = MagicMock()
        hass.states.get.return_value = None
        assert _read_eos_entity(hass, "sensor.test") is None

    def test_non_numeric(self):
        hass = MagicMock()
        state = MagicMock()
        state.state = "not_a_number"
        hass.states.get.return_value = state
        assert _read_eos_entity(hass, "sensor.test") is None


class TestCoordinatorOverrides:
    def test_set_and_clear_sg_ready_override(self):
        """Test SG-Ready override lifecycle."""
        MagicMock()
        entry = MagicMock()
        entry.data = {"eos_url": "http://localhost:8503"}
        entry.options = {}

        coordinator = EOSCoordinator.__new__(EOSCoordinator)
        # Manually init the override attributes
        coordinator._sg_ready_override_mode = None
        coordinator._sg_ready_override_until = None

        assert coordinator.sg_ready_override is None

        coordinator.set_sg_ready_override(3, 0)  # indefinite
        assert coordinator.sg_ready_override == 3

        coordinator.clear_sg_ready_override()
        assert coordinator.sg_ready_override is None

    def test_override_mode_set(self):
        coordinator = EOSCoordinator.__new__(EOSCoordinator)
        coordinator._override_mode = None
        coordinator._override_until = None

        assert coordinator.active_override is None

        coordinator.set_override("charge", 60)
        assert coordinator.active_override == "charge"

        coordinator.set_override("auto", 0)
        assert coordinator.active_override is None
