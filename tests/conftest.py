"""Fixtures for EOS HA tests."""
from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations):
    """Enable custom integrations for all tests."""
    yield


@pytest.fixture
def mock_eos_health():
    """Mock a successful EOS health check."""
    with patch(
        "aiohttp.ClientSession.get",
    ) as mock_get:
        mock_resp = AsyncMock()
        mock_resp.status = 200
        mock_resp.json = AsyncMock(return_value={"status": "alive", "version": "0.1.0"})
        mock_get.return_value.__aenter__ = AsyncMock(return_value=mock_resp)
        mock_get.return_value.__aexit__ = AsyncMock(return_value=False)
        yield mock_get
