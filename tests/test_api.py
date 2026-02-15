"""Tests for EOS HA API client."""
from custom_components.eos_ha.api import EOSApiClient, EOSConnectionError, EOSOptimizationError


def test_api_client_init():
    client = EOSApiClient(None, "http://localhost:8503/")
    assert client.base_url == "http://localhost:8503"


def test_api_client_strips_trailing_slash():
    client = EOSApiClient(None, "http://localhost:8503///")
    assert client.base_url == "http://localhost:8503"


def test_exceptions_exist():
    assert issubclass(EOSConnectionError, Exception)
    assert issubclass(EOSOptimizationError, Exception)
