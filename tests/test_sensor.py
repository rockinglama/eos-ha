"""Tests for EOS HA sensor platform."""
from __future__ import annotations



from custom_components.eos_ha.sensor import (
    EOSOptimizationStatusSensor,
    EOSSensor,
    EOSSGReadyModeSensor,
    SENSOR_DESCRIPTIONS,
    _current_hour_value,
    _derive_mode,
)
from custom_components.eos_ha.const import (
    CONF_SG_READY_SURPLUS_THRESHOLD,
)


class TestCurrentHourValue:
    def test_returns_first_element(self):
        assert _current_hour_value({"key": [1.234, 2.0]}, "key") == 1.23

    def test_empty_array(self):
        assert _current_hour_value({"key": []}, "key") is None

    def test_missing_key(self):
        assert _current_hour_value({}, "key") is None


class TestDeriveMode:
    def test_override_charge(self):
        assert _derive_mode({"active_override": "charge"}) == "Override: Charge"

    def test_override_discharge(self):
        assert _derive_mode({"active_override": "discharge"}) == "Override: Discharge"

    def test_grid_charge(self):
        assert _derive_mode({"ac_charge": [1.0], "discharge_allowed": [1]}) == "Grid Charge"

    def test_avoid_discharge(self):
        assert _derive_mode({"ac_charge": [0], "discharge_allowed": [0]}) == "Avoid Discharge"

    def test_allow_discharge(self):
        assert _derive_mode({"ac_charge": [0], "discharge_allowed": [1]}) == "Allow Discharge"

    def test_empty_data(self):
        assert _derive_mode({}) == "Allow Discharge"


class TestEOSSensor:
    def test_sensor_descriptions_exist(self):
        keys = [d.key for d in SENSOR_DESCRIPTIONS]
        assert "ac_charge_power" in keys
        assert "dc_charge_power" in keys
        assert "current_mode" in keys
        assert "pv_forecast" in keys
        assert "price_forecast" in keys
        assert "battery_soc_forecast" in keys
        assert "total_cost" in keys

    def test_sensor_value(self, mock_coordinator):
        desc = next(d for d in SENSOR_DESCRIPTIONS if d.key == "ac_charge_power")
        sensor = EOSSensor(mock_coordinator, desc)
        assert sensor.native_value == 0.5

    def test_sensor_no_data(self, mock_coordinator):
        mock_coordinator.data = None
        desc = next(d for d in SENSOR_DESCRIPTIONS if d.key == "ac_charge_power")
        sensor = EOSSensor(mock_coordinator, desc)
        assert sensor.native_value is None

    def test_unique_id(self, mock_coordinator):
        desc = next(d for d in SENSOR_DESCRIPTIONS if d.key == "ac_charge_power")
        sensor = EOSSensor(mock_coordinator, desc)
        assert sensor.unique_id == "test_entry_id_ac_charge_power"


class TestOptimizationStatusSensor:
    def test_optimized(self, mock_coordinator):
        sensor = EOSOptimizationStatusSensor(mock_coordinator)
        assert sensor.native_value == "optimized"

    def test_failed(self, mock_coordinator):
        mock_coordinator.data = {}
        mock_coordinator.last_update_success = False
        sensor = EOSOptimizationStatusSensor(mock_coordinator)
        assert sensor.native_value == "failed"

    def test_unknown(self, mock_coordinator):
        mock_coordinator.data = {}
        sensor = EOSOptimizationStatusSensor(mock_coordinator)
        assert sensor.native_value == "unknown"

    def test_attributes(self, mock_coordinator):
        sensor = EOSOptimizationStatusSensor(mock_coordinator)
        attrs = sensor.extra_state_attributes
        assert attrs["eos_server_url"] == "http://localhost:8503"


class TestSGReadyModeSensor:
    """Test SG-Ready mode computation with configurable surplus threshold."""

    def _make_sensor(self, coordinator, config_overrides=None):
        config = {**coordinator.config_entry.data, **coordinator.config_entry.options}
        if config_overrides:
            config.update(config_overrides)
        # Patch config_entry so _get_config reads overrides
        coordinator.config_entry.data = config
        coordinator.config_entry.options = {}
        return EOSSGReadyModeSensor(coordinator, config)

    def test_default_mode_is_normal(self, mock_coordinator):
        """Mode 2 when PV surplus < threshold and prices normal."""
        mock_coordinator.data = {
            "pv_forecast": [400],
            "price_forecast": [0.0003] * 24,
            "battery_soc_forecast": [50],
            "consumption_forecast": [300],
        }
        sensor = self._make_sensor(mock_coordinator)
        assert sensor.native_value == 2

    def test_mode3_default_threshold(self, mock_coordinator):
        """Mode 3 when PV surplus > 500W (default threshold)."""
        mock_coordinator.data = {
            "pv_forecast": [2000],
            "price_forecast": [0.0003] * 24,
            "battery_soc_forecast": [50],
            "consumption_forecast": [500],
        }
        sensor = self._make_sensor(mock_coordinator)
        # surplus = 2000 - 500 = 1500 > 500
        assert sensor.native_value == 3

    def test_mode3_custom_threshold_not_met(self, mock_coordinator):
        """Mode 2 when surplus < custom threshold (1000W)."""
        mock_coordinator.data = {
            "pv_forecast": [1200],
            "price_forecast": [0.0003] * 24,
            "battery_soc_forecast": [50],
            "consumption_forecast": [500],
        }
        sensor = self._make_sensor(
            mock_coordinator,
            {CONF_SG_READY_SURPLUS_THRESHOLD: 1000},
        )
        # surplus = 1200 - 500 = 700 < 1000
        assert sensor.native_value == 2

    def test_mode3_custom_threshold_met(self, mock_coordinator):
        """Mode 3 when surplus > custom threshold (1000W)."""
        mock_coordinator.data = {
            "pv_forecast": [2500],
            "price_forecast": [0.0003] * 24,
            "battery_soc_forecast": [50],
            "consumption_forecast": [500],
        }
        sensor = self._make_sensor(
            mock_coordinator,
            {CONF_SG_READY_SURPLUS_THRESHOLD: 1000},
        )
        # surplus = 2500 - 500 = 2000 > 1000
        assert sensor.native_value == 3

    def test_mode4_surplus_and_battery_full(self, mock_coordinator):
        """Mode 4 when surplus > threshold AND SOC > max_soc - 5."""
        mock_coordinator.data = {
            "pv_forecast": [3000],
            "price_forecast": [0.0003] * 24,
            "battery_soc_forecast": [87],  # > 90 - 5 = 85
            "consumption_forecast": [500],
        }
        sensor = self._make_sensor(mock_coordinator)
        # surplus = 2500 > 500, SOC 87 > 85
        assert sensor.native_value == 4

    def test_mode4_custom_threshold(self, mock_coordinator):
        """Mode 4 with custom threshold 1000W."""
        mock_coordinator.data = {
            "pv_forecast": [3000],
            "price_forecast": [0.0003] * 24,
            "battery_soc_forecast": [87],
            "consumption_forecast": [500],
        }
        sensor = self._make_sensor(
            mock_coordinator,
            {CONF_SG_READY_SURPLUS_THRESHOLD: 1000},
        )
        # surplus = 2500 > 1000, SOC 87 > 85
        assert sensor.native_value == 4

    def test_mode4_custom_threshold_not_met_falls_to_mode2(self, mock_coordinator):
        """Surplus below custom threshold → Mode 2 even with full battery."""
        mock_coordinator.data = {
            "pv_forecast": [1200],
            "price_forecast": [0.0003] * 24,
            "battery_soc_forecast": [87],
            "consumption_forecast": [500],
        }
        sensor = self._make_sensor(
            mock_coordinator,
            {CONF_SG_READY_SURPLUS_THRESHOLD: 1000},
        )
        # surplus = 700 < 1000
        assert sensor.native_value == 2

    def test_mode1_expensive_no_pv_low_soc(self, mock_coordinator):
        """Mode 1 (Lock) when expensive, no PV, low SOC."""
        avg_price = 0.0003
        mock_coordinator.data = {
            "pv_forecast": [50],  # < 100
            "price_forecast": [avg_price * 2] + [avg_price] * 23,  # current > 150% avg
            "battery_soc_forecast": [20],  # < min_soc(15) + 10 = 25
            "consumption_forecast": [500],
        }
        sensor = self._make_sensor(mock_coordinator)
        assert sensor.native_value == 1

    def test_mode3_cheap_electricity(self, mock_coordinator):
        """Mode 3 when electricity is very cheap (< 50% avg)."""
        avg_price = 0.001
        mock_coordinator.data = {
            "pv_forecast": [100],
            "price_forecast": [avg_price * 0.3] + [avg_price] * 23,
            "battery_soc_forecast": [50],
            "consumption_forecast": [500],
        }
        sensor = self._make_sensor(mock_coordinator)
        assert sensor.native_value == 3

    def test_manual_override(self, mock_coordinator):
        """Manual override takes precedence."""
        mock_coordinator.sg_ready_override = 4
        mock_coordinator.data = {
            "pv_forecast": [100],
            "price_forecast": [0.0003] * 24,
            "battery_soc_forecast": [50],
            "consumption_forecast": [500],
        }
        sensor = self._make_sensor(mock_coordinator)
        assert sensor.native_value == 4

    def test_no_data_returns_mode2(self, mock_coordinator):
        """No data → Mode 2."""
        mock_coordinator.data = None
        sensor = self._make_sensor(mock_coordinator)
        assert sensor.native_value == 2

    def test_attributes(self, mock_coordinator):
        """Check extra attributes include mode_name and reason."""
        mock_coordinator.data = {
            "pv_forecast": [3000],
            "price_forecast": [0.0003] * 24,
            "battery_soc_forecast": [50],
            "consumption_forecast": [500],
        }
        sensor = self._make_sensor(mock_coordinator)
        attrs = sensor.extra_state_attributes
        assert "mode_name" in attrs
        assert "reason" in attrs
        assert attrs["mode_name"] == "Recommend"
