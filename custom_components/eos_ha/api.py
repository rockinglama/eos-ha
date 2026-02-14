"""API client for EOS server."""
from __future__ import annotations

import asyncio
import logging
from typing import Any

import aiohttp

_LOGGER = logging.getLogger(__name__)


# Custom exceptions
class EOSConnectionError(Exception):
    """Error connecting to EOS server."""


class EOSOptimizationError(Exception):
    """Error during EOS optimization."""


class EOSApiClient:
    """Async client for EOS server API."""

    def __init__(self, session: aiohttp.ClientSession, base_url: str) -> None:
        self.session = session
        self.base_url = base_url.rstrip("/")

    async def validate_server(self) -> dict[str, Any]:
        """Validate EOS server connection by checking health endpoint."""
        try:
            timeout = aiohttp.ClientTimeout(total=10)
            async with self.session.get(
                f"{self.base_url}/v1/health",
                timeout=timeout,
            ) as resp:
                if resp.status != 200:
                    raise EOSConnectionError(f"Health check failed with status {resp.status}")
                data = await resp.json()
                if data.get("status") != "alive":
                    raise EOSConnectionError(f"Invalid health status: {data.get('status')}")
                return data
        except aiohttp.ClientError as err:
            raise EOSConnectionError(f"Connection error: {err}") from err
        except asyncio.TimeoutError as err:
            raise EOSConnectionError("Connection timeout") from err

    # ---- Config endpoints ----

    async def get_config(self, path: str | None = None) -> dict[str, Any]:
        """GET /v1/config or /v1/config/{path}."""
        url = f"{self.base_url}/v1/config"
        if path:
            url += f"/{path}"
        try:
            timeout = aiohttp.ClientTimeout(total=10)
            async with self.session.get(url, timeout=timeout) as resp:
                if resp.status != 200:
                    _LOGGER.error("GET %s returned %s", url, resp.status)
                    return {}
                return await resp.json()
        except (aiohttp.ClientError, asyncio.TimeoutError) as err:
            _LOGGER.error("Error fetching config %s: %s", path, err)
            return {}

    async def put_config(self, path: str, value: Any) -> dict[str, Any]:
        """PUT /v1/config/{path} with JSON body."""
        url = f"{self.base_url}/v1/config/{path}"
        try:
            timeout = aiohttp.ClientTimeout(total=10)
            async with self.session.put(
                url, json=value, timeout=timeout,
                headers={"Content-Type": "application/json"},
            ) as resp:
                if resp.status != 200:
                    body = await resp.text()
                    _LOGGER.error("PUT %s returned %s: %s", url, resp.status, body[:200])
                    return {}
                return await resp.json()
        except (aiohttp.ClientError, asyncio.TimeoutError) as err:
            _LOGGER.error("Error putting config %s: %s", path, err)
            return {}

    # ---- Prediction update ----

    async def update_predictions(self, force_update: bool = True) -> bool:
        """POST /v1/prediction/update — trigger EOS to recalculate all predictions."""
        url = f"{self.base_url}/v1/prediction/update"
        params = {"force_update": str(force_update).lower()}
        try:
            timeout = aiohttp.ClientTimeout(total=60)
            async with self.session.post(url, params=params, timeout=timeout) as resp:
                if resp.status != 200:
                    body = await resp.text()
                    _LOGGER.error("POST /v1/prediction/update returned %s: %s", resp.status, body[:200])
                    return False
                _LOGGER.info("Predictions updated successfully")
                return True
        except (aiohttp.ClientError, asyncio.TimeoutError) as err:
            _LOGGER.error("Error updating predictions: %s", err)
            return False

    # ---- Prediction import ----

    async def import_prediction(
        self, provider_id: str, data: Any, force_enable: bool = True,
    ) -> bool:
        """PUT /v1/prediction/import/{provider_id} — push external prediction data."""
        url = f"{self.base_url}/v1/prediction/import/{provider_id}"
        params = {}
        if force_enable:
            params["force_enable"] = "true"
        try:
            timeout = aiohttp.ClientTimeout(total=15)
            async with self.session.put(
                url, json=data, params=params, timeout=timeout,
                headers={"Content-Type": "application/json"},
            ) as resp:
                if resp.status != 200:
                    body = await resp.text()
                    _LOGGER.error("PUT prediction import %s returned %s: %s", provider_id, resp.status, body[:200])
                    return False
                return True
        except (aiohttp.ClientError, asyncio.TimeoutError) as err:
            _LOGGER.error("Error importing prediction %s: %s", provider_id, err)
            return False

    # ---- Prediction series ----

    async def get_prediction_series(self, key: str) -> dict[str, Any]:
        """GET /v1/prediction/series?key=... — get a prediction time series."""
        url = f"{self.base_url}/v1/prediction/series"
        params = {"key": key}
        try:
            timeout = aiohttp.ClientTimeout(total=10)
            async with self.session.get(url, params=params, timeout=timeout) as resp:
                if resp.status != 200:
                    _LOGGER.debug("GET prediction series %s returned %s", key, resp.status)
                    return {}
                return await resp.json()
        except (aiohttp.ClientError, asyncio.TimeoutError) as err:
            _LOGGER.debug("Error fetching prediction series %s: %s", key, err)
            return {}

    # ---- Measurement ----

    async def put_measurement_value(self, dt_str: str, key: str, value: float) -> bool:
        """PUT /v1/measurement/value?datetime=...&key=...&value=..."""
        url = f"{self.base_url}/v1/measurement/value"
        params = {"datetime": dt_str, "key": key, "value": str(value)}
        try:
            timeout = aiohttp.ClientTimeout(total=10)
            async with self.session.put(url, params=params, timeout=timeout) as resp:
                if resp.status != 200:
                    body = await resp.text()
                    _LOGGER.debug("PUT measurement %s=%s returned %s: %s", key, value, resp.status, body[:200])
                    return False
                return True
        except (aiohttp.ClientError, asyncio.TimeoutError) as err:
            _LOGGER.debug("Error pushing measurement %s: %s", key, err)
            return False

    # ---- Resource status ----

    async def get_resource_status(self, resource_id: str) -> dict[str, Any]:
        """GET /v1/resource/status?resource_id=..."""
        url = f"{self.base_url}/v1/resource/status"
        params = {"resource_id": resource_id}
        try:
            timeout = aiohttp.ClientTimeout(total=10)
            async with self.session.get(url, params=params, timeout=timeout) as resp:
                if resp.status != 200:
                    _LOGGER.debug("GET resource status %s returned %s", resource_id, resp.status)
                    return {}
                return await resp.json()
        except (aiohttp.ClientError, asyncio.TimeoutError) as err:
            _LOGGER.debug("Error fetching resource status %s: %s", resource_id, err)
            return {}

    # ---- Energy management ----

    async def get_energy_plan(self) -> dict[str, Any]:
        """GET /v1/energy-management/plan."""
        url = f"{self.base_url}/v1/energy-management/plan"
        try:
            timeout = aiohttp.ClientTimeout(total=10)
            async with self.session.get(url, timeout=timeout) as resp:
                if resp.status != 200:
                    _LOGGER.debug("GET energy plan returned %s", resp.status)
                    return {}
                return await resp.json()
        except (aiohttp.ClientError, asyncio.TimeoutError) as err:
            _LOGGER.debug("Error fetching energy plan: %s", err)
            return {}

    async def get_optimization_solution(self) -> dict[str, Any]:
        """GET /v1/energy-management/optimization/solution."""
        url = f"{self.base_url}/v1/energy-management/optimization/solution"
        try:
            timeout = aiohttp.ClientTimeout(total=15)
            async with self.session.get(url, timeout=timeout) as resp:
                if resp.status != 200:
                    _LOGGER.debug("GET optimization solution returned %s", resp.status)
                    return {}
                return await resp.json()
        except (aiohttp.ClientError, asyncio.TimeoutError) as err:
            _LOGGER.debug("Error fetching optimization solution: %s", err)
            return {}
