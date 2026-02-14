"""API clients for EOS server and Akkudoktor."""
from __future__ import annotations

import asyncio
from datetime import timedelta
import logging
from typing import Any

import aiohttp

from homeassistant.util import dt as dt_util

from .const import AKKUDOKTOR_API_URL

_LOGGER = logging.getLogger(__name__)


# Custom exceptions
class EOSConnectionError(Exception):
    """Error connecting to EOS server."""
    pass


class EOSOptimizationError(Exception):
    """Error during EOS optimization."""
    pass


class AkkudoktorApiError(Exception):
    """Error fetching data from Akkudoktor API."""
    pass


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

    async def optimize(self, eos_request: dict[str, Any], start_hour: int) -> dict[str, Any]:
        """Send optimization request to EOS server."""
        headers = {
            "accept": "application/json",
            "Content-Type": "application/json",
        }
        try:
            timeout = aiohttp.ClientTimeout(total=180)
            url = f"{self.base_url}/optimize?start_hour={start_hour}"
            _LOGGER.debug("Sending optimization request to %s", url)
            async with self.session.post(
                url, json=eos_request, headers=headers, timeout=timeout,
            ) as resp:
                if resp.status != 200:
                    raise EOSOptimizationError(f"EOS returned status {resp.status}")
                return await resp.json()
        except aiohttp.ClientError as err:
            raise EOSConnectionError(f"Connection error during optimization: {err}") from err
        except asyncio.TimeoutError as err:
            raise EOSOptimizationError("EOS optimization timed out") from err

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

    # ---- Strompreis endpoint ----

    async def get_strompreis(self) -> list[float]:
        """GET /strompreis — returns 48h price forecast in EUR/Wh."""
        url = f"{self.base_url}/strompreis"
        try:
            timeout = aiohttp.ClientTimeout(total=15)
            async with self.session.get(url, timeout=timeout) as resp:
                if resp.status != 200:
                    _LOGGER.error("GET /strompreis returned %s", resp.status)
                    return []
                data = await resp.json()
                if isinstance(data, list):
                    return data
                _LOGGER.error("Unexpected strompreis response type: %s", type(data))
                return []
        except (aiohttp.ClientError, asyncio.TimeoutError) as err:
            _LOGGER.error("Error fetching strompreis: %s", err)
            return []

    # ---- PV Forecast endpoint ----

    async def get_pvforecast(self) -> list[float]:
        """GET /pvforecast — returns 48h PV forecast in W."""
        url = f"{self.base_url}/pvforecast"
        try:
            timeout = aiohttp.ClientTimeout(total=30)
            async with self.session.get(url, timeout=timeout) as resp:
                if resp.status != 200:
                    body = await resp.text()
                    _LOGGER.error("GET /pvforecast returned %s: %s", resp.status, body[:200])
                    return []
                data = await resp.json()
                if isinstance(data, list):
                    return data
                if isinstance(data, dict) and "pvpower" in data:
                    return data["pvpower"]
                _LOGGER.error("Unexpected pvforecast response type: %s", type(data))
                return []
        except (aiohttp.ClientError, asyncio.TimeoutError) as err:
            _LOGGER.error("Error fetching pvforecast: %s", err)
            return []

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

    # ---- Energy management plan ----

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


class AkkudoktorApiClient:
    """Async client for Akkudoktor PV forecast API."""

    def __init__(self, session: aiohttp.ClientSession) -> None:
        self.session = session

    async def get_pv_forecast(
        self,
        lat: float,
        lon: float,
        pv_arrays: list[dict] | None = None,
        timezone: str = "UTC",
    ) -> list[float]:
        """Fetch 48-hour PV forecast from Akkudoktor API."""
        if not pv_arrays:
            pv_arrays = [{"azimuth": 180, "tilt": 30, "power": 1000, "inverter_power": 1000}]

        params = f"?lat={lat}&lon={lon}&timezone={timezone}"
        for arr in pv_arrays:
            params += (
                f"&azimuth={arr['azimuth']}"
                f"&tilt={arr['tilt']}"
                f"&power={arr['power']}"
                f"&powerInverter={arr.get('inverter_power', arr['power'])}"
                f"&inverterEfficiency={arr.get('inverter_efficiency', 0.9)}"
            )
        url = f"{AKKUDOKTOR_API_URL}{params}"

        try:
            timeout = aiohttp.ClientTimeout(total=10)
            _LOGGER.debug("Fetching PV forecast from Akkudoktor API")
            async with self.session.get(url, timeout=timeout) as resp:
                if resp.status != 200:
                    raise AkkudoktorApiError(f"Akkudoktor API returned status {resp.status}")
                data = await resp.json(content_type=None)

            forecast_values = []
            current_time = dt_util.now().replace(hour=0, minute=0, second=0, microsecond=0)
            end_time = current_time + timedelta(hours=48)

            for forecast_entry in data.get("values", []):
                for forecast in forecast_entry:
                    entry_time = dt_util.parse_datetime(forecast["datetime"])
                    if entry_time is None:
                        continue
                    if current_time <= entry_time < end_time:
                        value = forecast.get("power", 0)
                        if value < 0:
                            value = 0
                        forecast_values.append(value)

            if forecast_values:
                forecast_values.pop(0)
                forecast_values.append(0)

            if len(forecast_values) > 48:
                forecast_values = forecast_values[:48]
            elif len(forecast_values) < 48:
                if forecast_values:
                    forecast_values.extend([forecast_values[-1]] * (48 - len(forecast_values)))
                else:
                    forecast_values = [0.0] * 48

            _LOGGER.debug("PV forecast fetched successfully: %s values", len(forecast_values))
            return forecast_values

        except aiohttp.ClientError as err:
            raise AkkudoktorApiError(f"Connection error: {err}") from err
        except asyncio.TimeoutError as err:
            raise AkkudoktorApiError("Request timeout") from err
        except (ValueError, TypeError, KeyError) as err:
            raise AkkudoktorApiError(f"Error processing forecast data: {err}") from err
