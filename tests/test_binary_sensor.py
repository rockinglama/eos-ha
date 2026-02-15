"""Tests for EOS HA binary sensor platform."""
from custom_components.eos_ha.binary_sensor import EOSDischargeAllowedSensor


class TestDischargeAllowedSensor:
    def test_discharge_allowed(self, mock_coordinator):
        sensor = EOSDischargeAllowedSensor(mock_coordinator)
        assert sensor.is_on is True

    def test_discharge_not_allowed(self, mock_coordinator):
        mock_coordinator.data = {"discharge_allowed": [False]}
        sensor = EOSDischargeAllowedSensor(mock_coordinator)
        assert sensor.is_on is False

    def test_no_data(self, mock_coordinator):
        mock_coordinator.data = None
        sensor = EOSDischargeAllowedSensor(mock_coordinator)
        assert sensor.is_on is None

    def test_empty_forecast(self, mock_coordinator):
        mock_coordinator.data = {"discharge_allowed": []}
        sensor = EOSDischargeAllowedSensor(mock_coordinator)
        assert sensor.is_on is None

    def test_unique_id(self, mock_coordinator):
        sensor = EOSDischargeAllowedSensor(mock_coordinator)
        assert sensor.unique_id == "test_entry_id_discharge_allowed"

    def test_attributes(self, mock_coordinator):
        mock_coordinator.data = {"discharge_allowed": [True, False, True]}
        sensor = EOSDischargeAllowedSensor(mock_coordinator)
        attrs = sensor.extra_state_attributes
        assert attrs["forecast"] == [True, False, True]

    def test_attributes_no_data(self, mock_coordinator):
        mock_coordinator.data = None
        sensor = EOSDischargeAllowedSensor(mock_coordinator)
        assert sensor.extra_state_attributes == {}
