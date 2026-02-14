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
        """Initialize the EOS API client.

        Args:
            session: aiohttp ClientSession for making requests
            base_url: Base URL of the EOS server (e.g., http://localhost:8503)
        """
        self.session = session
        self.base_url = base_url.rstrip("/")

    async def validate_server(self) -> dict[str, Any]:
        """Validate EOS server connection by checking health endpoint.

        Returns:
            Health response JSON containing status and version info

        Raises:
            EOSConnectionError: If server is unreachable or returns invalid response
        """
        try:
            timeout = aiohttp.ClientTimeout(total=10)
            async with self.session.get(
                f"{self.base_url}/v1/health",
                timeout=timeout,
            ) as resp:
                if resp.status != 200:
                    raise EOSConnectionError(f"Health check failed with status {resp.status}")

                data = await resp.json()

                # Check for expected "alive" status
                if data.get("status") != "alive":
                    raise EOSConnectionError(f"Invalid health status: {data.get('status')}")

                return data

        except aiohttp.ClientError as err:
            raise EOSConnectionError(f"Connection error: {err}") from err
        except asyncio.TimeoutError as err:
            raise EOSConnectionError("Connection timeout") from err

    async def optimize(self, eos_request: dict[str, Any], start_hour: int) -> dict[str, Any]:
        """Send optimization request to EOS server.

        Args:
            eos_request: EOS-format optimization request payload
            start_hour: Current hour (0-23) to start optimization from

        Returns:
            Optimization response JSON with ac_charge, dc_charge, discharge_allowed, etc.

        Raises:
            EOSOptimizationError: If optimization fails or times out
            EOSConnectionError: If connection to server fails
        """
        headers = {
            "accept": "application/json",
            "Content-Type": "application/json",
        }

        try:
            timeout = aiohttp.ClientTimeout(total=180)
            url = f"{self.base_url}/optimize?start_hour={start_hour}"

            _LOGGER.debug("Sending optimization request to %s", url)

            async with self.session.post(
                url,
                json=eos_request,
                headers=headers,
                timeout=timeout,
            ) as resp:
                if resp.status != 200:
                    raise EOSOptimizationError(f"EOS returned status {resp.status}")

                return await resp.json()

        except aiohttp.ClientError as err:
            raise EOSConnectionError(f"Connection error during optimization: {err}") from err
        except asyncio.TimeoutError as err:
            raise EOSOptimizationError("EOS optimization timed out") from err


class AkkudoktorApiClient:
    """Async client for Akkudoktor PV forecast API."""

    def __init__(self, session: aiohttp.ClientSession) -> None:
        """Initialize the Akkudoktor API client.

        Args:
            session: aiohttp ClientSession for making requests
        """
        self.session = session

    async def get_pv_forecast(
        self,
        lat: float,
        lon: float,
        azimuth: float = 180,
        tilt: float = 30,
        power: float = 1000,
        power_inverter: float = 1000,
        inverter_efficiency: float = 1.0,
        timezone: str = "UTC",
    ) -> list[float]:
        """Fetch 48-hour PV forecast from Akkudoktor API.

        Args:
            lat: Latitude
            lon: Longitude
            azimuth: Panel azimuth in degrees (default 180 = south)
            tilt: Panel tilt in degrees (default 30)
            power: Panel power in W (default 1000)
            power_inverter: Inverter power in W (default 1000)
            inverter_efficiency: Inverter efficiency 0-1 (default 1.0)
            timezone: Timezone string (default UTC)

        Returns:
            List of 48 hourly PV power forecast values in W

        Raises:
            AkkudoktorApiError: If API request fails or data processing fails
        """
        # Build request URL with query parameters matching existing pattern
        url = (
            f"{AKKUDOKTOR_API_URL}"
            f"?lat={lat}"
            f"&lon={lon}"
            f"&azimuth={azimuth}"
            f"&tilt={tilt}"
            f"&power={power}"
            f"&powerInverter={power_inverter}"
            f"&inverterEfficiency={inverter_efficiency}"
            f"&timezone={timezone}"
        )

        try:
            timeout = aiohttp.ClientTimeout(total=10)

            _LOGGER.debug("Fetching PV forecast from Akkudoktor API")

            async with self.session.get(url, timeout=timeout) as resp:
                if resp.status != 200:
                    raise AkkudoktorApiError(f"Akkudoktor API returned status {resp.status}")

                # Akkudoktor API incorrectly returns content-type: text/html for JSON responses
                # Use content_type=None to skip content-type validation
                data = await resp.json(content_type=None)

            # Process response into 48-hour hourly array
            # Following pattern from pv_interface.py lines 691-776
            forecast_values = []

            # Get current midnight in configured timezone
            current_time = dt_util.now().replace(hour=0, minute=0, second=0, microsecond=0)
            end_time = current_time + timedelta(hours=48)

            # Extract values from nested structure
            # data["values"] is list of lists of dicts with "datetime" and "power" keys
            for forecast_entry in data.get("values", []):
                for forecast in forecast_entry:
                    # Parse datetime
                    entry_time = dt_util.parse_datetime(forecast["datetime"])
                    if entry_time is None:
                        continue

                    # Filter to midnight today through 48 hours ahead
                    if current_time <= entry_time < end_time:
                        value = forecast.get("power", 0)
                        # Clamp negative values to 0 (API sometimes returns negatives)
                        if value < 0:
                            value = 0
                        forecast_values.append(value)

            # Apply workaround: remove first entry and append 0
            # This fixes wrong time points in Akkudoktor forecast
            if forecast_values:
                forecast_values.pop(0)
                forecast_values.append(0)

            # Pad or trim to exactly 48 values
            if len(forecast_values) > 48:
                forecast_values = forecast_values[:48]
                _LOGGER.debug("PV forecast reduced to 48 values (had %s)", len(forecast_values) + 48)
            elif len(forecast_values) < 48:
                if forecast_values:
                    # Extend with last value
                    forecast_values.extend([forecast_values[-1]] * (48 - len(forecast_values)))
                else:
                    # No data at all, use zeros
                    forecast_values = [0.0] * 48
                _LOGGER.debug("PV forecast extended to 48 values (had %s)", len(forecast_values) - (48 - len(forecast_values)))

            _LOGGER.debug("PV forecast fetched successfully: %s values", len(forecast_values))
            return forecast_values

        except aiohttp.ClientError as err:
            raise AkkudoktorApiError(f"Connection error: {err}") from err
        except asyncio.TimeoutError as err:
            raise AkkudoktorApiError("Request timeout") from err
        except (ValueError, TypeError, KeyError) as err:
            raise AkkudoktorApiError(f"Error processing forecast data: {err}") from err


