"""Tests for EOS HA switch platform — SG-Ready auto control."""
from __future__ import annotations



from custom_components.eos_ha.switch import (
    EOSSGReadySwitch,
    SG_READY_RELAY_MAP,
)
from custom_components.eos_ha.const import (
    CONF_SG_READY_SURPLUS_THRESHOLD,
    DEFAULT_SG_READY_SURPLUS_THRESHOLD,
)


class TestSGReadyRelayMap:
    def test_mode1_lock(self):
        assert SG_READY_RELAY_MAP[1] == (True, False)

    def test_mode2_normal(self):
        assert SG_READY_RELAY_MAP[2] == (False, False)

    def test_mode3_recommend(self):
        assert SG_READY_RELAY_MAP[3] == (False, True)

    def test_mode4_force(self):
        assert SG_READY_RELAY_MAP[4] == (True, True)


class TestSGReadySwitch:
    def _make_switch(self, coordinator, config_overrides=None):
        config = {**coordinator.config_entry.data, **coordinator.config_entry.options}
        if config_overrides:
            config.update(config_overrides)
            coordinator.config_entry.data = config
            coordinator.config_entry.options = {}
        return EOSSGReadySwitch(coordinator, config)

    def test_initial_state_off(self, mock_coordinator):
        switch = self._make_switch(mock_coordinator)
        assert switch.is_on is False

    def test_unique_id(self, mock_coordinator):
        switch = self._make_switch(mock_coordinator)
        assert switch.unique_id == "test_entry_id_sg_ready_auto"

    def test_compute_mode_normal(self, mock_coordinator):
        """Mode 2 when no surplus."""
        mock_coordinator.data = {
            "pv_forecast": [400],
            "price_forecast": [0.0003] * 24,
            "battery_soc_forecast": [50],
            "consumption_forecast": [300],
        }
        switch = self._make_switch(mock_coordinator)
        assert switch._compute_recommended_mode() == 2

    def test_compute_mode3_surplus(self, mock_coordinator):
        """Mode 3 when PV surplus > default threshold."""
        mock_coordinator.data = {
            "pv_forecast": [2000],
            "price_forecast": [0.0003] * 24,
            "battery_soc_forecast": [50],
            "consumption_forecast": [500],
        }
        switch = self._make_switch(mock_coordinator)
        assert switch._compute_recommended_mode() == 3

    def test_compute_mode4_surplus_and_full_battery(self, mock_coordinator):
        """Mode 4 when surplus > threshold AND battery near full."""
        mock_coordinator.data = {
            "pv_forecast": [3000],
            "price_forecast": [0.0003] * 24,
            "battery_soc_forecast": [87],
            "consumption_forecast": [500],
        }
        switch = self._make_switch(mock_coordinator)
        assert switch._compute_recommended_mode() == 4

    def test_compute_mode_custom_threshold(self, mock_coordinator):
        """Custom threshold 1000W: surplus 700W → Mode 2."""
        mock_coordinator.data = {
            "pv_forecast": [1200],
            "price_forecast": [0.0003] * 24,
            "battery_soc_forecast": [50],
            "consumption_forecast": [500],
        }
        switch = self._make_switch(
            mock_coordinator,
            {CONF_SG_READY_SURPLUS_THRESHOLD: 1000},
        )
        assert switch._compute_recommended_mode() == 2

    def test_compute_mode_with_override(self, mock_coordinator):
        """Override takes precedence."""
        mock_coordinator.sg_ready_override = 3
        mock_coordinator.data = {
            "pv_forecast": [100],
            "price_forecast": [0.0003] * 24,
            "battery_soc_forecast": [50],
            "consumption_forecast": [500],
        }
        switch = self._make_switch(mock_coordinator)
        assert switch._compute_recommended_mode() == 3

    def test_attributes(self, mock_coordinator):
        switch = self._make_switch(mock_coordinator)
        attrs = switch.extra_state_attributes
        assert "surplus_threshold_w" in attrs
        assert attrs["surplus_threshold_w"] == DEFAULT_SG_READY_SURPLUS_THRESHOLD
        assert attrs["mode_name"] == "Inactive"

    def test_attributes_custom_threshold(self, mock_coordinator):
        switch = self._make_switch(
            mock_coordinator,
            {CONF_SG_READY_SURPLUS_THRESHOLD: 1000},
        )
        attrs = switch.extra_state_attributes
        assert attrs["surplus_threshold_w"] == 1000
