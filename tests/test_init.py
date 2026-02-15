"""Tests for EOS HA __init__ module."""
from custom_components.eos_ha import PLATFORMS
from custom_components.eos_ha.const import DOMAIN


def test_domain():
    assert DOMAIN == "eos_ha"


def test_platforms():
    assert "sensor" in PLATFORMS
    assert "binary_sensor" in PLATFORMS
    assert "number" in PLATFORMS
    assert "switch" in PLATFORMS
    assert "button" in PLATFORMS
