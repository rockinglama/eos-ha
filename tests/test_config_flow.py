"""Tests for EOS HA config flow."""
from custom_components.eos_ha.config_flow import EOSHAConfigFlow, EOSHAOptionsFlow


def test_config_flow_class_exists():
    """Config flow class can be instantiated."""
    flow = EOSHAConfigFlow()
    assert flow.VERSION == 1
    assert flow.data == {}


def test_options_flow_class_exists():
    """Options flow class can be instantiated."""
    flow = EOSHAOptionsFlow()
    assert flow._pv_arrays == []
    assert flow._pending == {}


def test_price_source_options():
    from custom_components.eos_ha.config_flow import PRICE_SOURCE_OPTIONS
    values = [o["value"] for o in PRICE_SOURCE_OPTIONS]
    assert "akkudoktor" in values
    assert "energycharts" in values
    assert "tibber" in values
    assert "external" in values
