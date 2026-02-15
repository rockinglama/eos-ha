"""Tests for EOS HA constants."""
from custom_components.eos_ha.const import (
    CONF_TIBBER_API_KEY,
    DEFAULT_SG_READY_SURPLUS_THRESHOLD,
    DEFAULT_BATTERY_CAPACITY,
    DEFAULT_MAX_SOC,
    DEFAULT_MIN_SOC,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
    PRICE_SOURCE_TIBBER,
    SG_READY_MODES,
    TIBBER_API_URL,
)


def test_domain():
    assert DOMAIN == "eos_ha"


def test_sg_ready_modes():
    assert SG_READY_MODES == {1: "Lock", 2: "Normal", 3: "Recommend", 4: "Force"}


def test_defaults():
    assert DEFAULT_SG_READY_SURPLUS_THRESHOLD == 500
    assert DEFAULT_BATTERY_CAPACITY == 10.0
    assert DEFAULT_MAX_SOC == 90
    assert DEFAULT_MIN_SOC == 15
    assert DEFAULT_SCAN_INTERVAL == 300


def test_tibber_constants():
    assert PRICE_SOURCE_TIBBER == "tibber"
    assert CONF_TIBBER_API_KEY == "tibber_api_key"
    assert TIBBER_API_URL == "https://api.tibber.com/v1-beta/gql"
