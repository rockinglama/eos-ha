"""DataUpdateCoordinator for EOS Connect integration."""
from __future__ import annotations

from datetime import timedelta
import logging
from typing import Any

import aiohttp

from homeassistant.const import STATE_UNAVAILABLE, STATE_UNKNOWN
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util

from .api import (
    AkkudoktorApiClient,
    AkkudoktorApiError,
    EOSApiClient,
    EOSConnectionError,
    EOSOptimizationError,
)
from .const import (
    CONF_BATTERY_CAPACITY,
    CONF_CONSUMPTION_ENTITY,
    CONF_EOS_URL,
    CONF_INVERTER_POWER,
    CONF_MAX_CHARGE_POWER,
    CONF_MAX_SOC,
    CONF_MIN_SOC,
    CONF_PRICE_ENTITY,
    CONF_SOC_ENTITY,
    DEFAULT_SCAN_INTERVAL,
    PV_FORECAST_CACHE_HOURS,
)

_LOGGER = logging.getLogger(__name__)


class EOSCoordinator(DataUpdateCoordinator):
    """DataUpdateCoordinator to manage EOS optimization cycle."""

    def __init__(self, hass: HomeAssistant, config_entry) -> None:
        """Initialize the coordinator.

        Args:
            hass: Home Assistant instance
            config_entry: ConfigEntry with user configuration
        """
        super().__init__(
            hass,
            _LOGGER,
            name="EOS Optimization",
            update_interval=timedelta(seconds=DEFAULT_SCAN_INTERVAL),
        )

        self.config_entry = config_entry

        # Create shared aiohttp session for all API calls
        self.session = aiohttp.ClientSession()

        # Initialize API clients
        self._eos_client = EOSApiClient(
            self.session,
            config_entry.data[CONF_EOS_URL],
        )
        self._akkudoktor_client = AkkudoktorApiClient(self.session)

        # PV forecast cache
        self._pv_forecast_cache: list[float] | None = None
        self._pv_forecast_timestamp = None

    async def _async_update_data(self) -> dict[str, Any]:
        """Fetch data from HA entities and run optimization cycle.

        This is the core optimization cycle that runs every 5 minutes.

        Returns:
            Dict containing optimization results and metadata

        Raises:
            UpdateFailed: If optimization cannot proceed
        """
        # Step 1: Read HA input entities
        price_entity = self.config_entry.data[CONF_PRICE_ENTITY]
        soc_entity = self.config_entry.data[CONF_SOC_ENTITY]
        consumption_entity = self.config_entry.data[CONF_CONSUMPTION_ENTITY]

        price_state = self.hass.states.get(price_entity)
        soc_state = self.hass.states.get(soc_entity)
        consumption_state = self.hass.states.get(consumption_entity)

        # Check for unavailable entities
        unavailable_entities = []
        if price_state is None or price_state.state in (STATE_UNAVAILABLE, STATE_UNKNOWN):
            unavailable_entities.append(f"price ({price_entity})")
        if soc_state is None or soc_state.state in (STATE_UNAVAILABLE, STATE_UNKNOWN):
            unavailable_entities.append(f"SOC ({soc_entity})")
        if consumption_state is None or consumption_state.state in (STATE_UNAVAILABLE, STATE_UNKNOWN):
            unavailable_entities.append(f"consumption ({consumption_entity})")

        if unavailable_entities:
            _LOGGER.debug(
                "Required entities unavailable: %s. Skipping optimization, keeping last valid data.",
                ", ".join(unavailable_entities),
            )
            # Return last valid data if available
            if self.data:
                return self.data
            # No previous data, raise error
            raise UpdateFailed(f"Required input entities unavailable: {', '.join(unavailable_entities)}")

        # Step 2: Fetch PV forecast with caching
        pv_forecast = await self._get_pv_forecast_cached()
        if pv_forecast is None:
            raise UpdateFailed("PV forecast unavailable and cache expired")

        # Step 3: Build EOS request
        eos_request = self._build_eos_request(
            price_state,
            soc_state,
            consumption_state,
            pv_forecast,
        )

        # Step 4: Send optimization
        try:
            current_hour = dt_util.now().hour
            result = await self._eos_client.optimize(eos_request, current_hour)
        except (EOSConnectionError, EOSOptimizationError) as err:
            raise UpdateFailed(str(err)) from err

        # Step 5: Parse response
        return self._parse_optimization_response(result)

    async def _get_pv_forecast_cached(self) -> list[float] | None:
        """Get PV forecast with 6-hour caching.

        Returns:
            48-hour PV forecast array, or None if API down and no cache available

        Raises:
            Does not raise - returns None on failure
        """
        # Check cache validity (6 hours)
        cache_valid = False
        if self._pv_forecast_cache and self._pv_forecast_timestamp:
            age = dt_util.now() - self._pv_forecast_timestamp
            if age < timedelta(hours=PV_FORECAST_CACHE_HOURS):
                cache_valid = True

        if cache_valid:
            _LOGGER.debug("Using cached PV forecast")
            return self._pv_forecast_cache

        # Cache invalid or missing, fetch from API
        try:
            # Get location from config entry
            # Config Flow stores these from hass.config
            lat = self.config_entry.data.get("latitude")
            lon = self.config_entry.data.get("longitude")

            if lat is None or lon is None:
                _LOGGER.error("Latitude/longitude not found in config entry")
                # Return expired cache if available
                if self._pv_forecast_cache:
                    _LOGGER.warning("Using expired cache due to missing location")
                    return self._pv_forecast_cache
                return None

            forecast = await self._akkudoktor_client.get_pv_forecast(
                lat=lat,
                lon=lon,
                timezone=self.hass.config.time_zone,
            )

            # Update cache
            self._pv_forecast_cache = forecast
            self._pv_forecast_timestamp = dt_util.now()

            _LOGGER.debug("PV forecast refreshed and cached")
            return forecast

        except AkkudoktorApiError as err:
            _LOGGER.warning("Akkudoktor API error: %s", err)
            # Return cached data even if expired
            if self._pv_forecast_cache:
                _LOGGER.info("Using expired PV forecast cache due to API error")
                return self._pv_forecast_cache
            # No cache at all
            return None

    def _build_eos_request(
        self,
        price_state,
        soc_state,
        consumption_state,
        pv_forecast: list[float],
    ) -> dict[str, Any]:
        """Build EOS optimization request from entity states and forecast.

        Args:
            price_state: Price entity state
            soc_state: Battery SOC entity state
            consumption_state: Consumption entity state
            pv_forecast: 48-hour PV forecast array

        Returns:
            EOS request dict matching existing format
        """
        return {
            "ems": {
                "pv_prognose_wh": pv_forecast,
                "strompreis_euro_pro_wh": self._extract_price_forecast(price_state),
                "einspeiseverguetung_euro_pro_wh": [0.0] * 48,  # Feed-in tariff, 0 for v1
                "preis_euro_pro_wh_akku": 0.0,  # Battery cost per Wh, 0 for v1
                "gesamtlast": self._extract_consumption_forecast(consumption_state),
            },
            "pv_akku": {
                # CRITICAL: Convert kWh (user input) to Wh (EOS expects)
                "capacity_wh": self.config_entry.data[CONF_BATTERY_CAPACITY] * 1000,
                "charging_efficiency": 0.95,  # Default efficiency
                "discharging_efficiency": 0.95,
                "max_charge_power_w": self.config_entry.data[CONF_MAX_CHARGE_POWER],
                "initial_soc_percentage": round(float(soc_state.state)),
                "min_soc_percentage": self.config_entry.data[CONF_MIN_SOC],
                "max_soc_percentage": self.config_entry.data[CONF_MAX_SOC],
            },
            "inverter": {
                "max_power_wh": self.config_entry.data[CONF_INVERTER_POWER],
            },
            # Default temperature forecast (15 degrees, matching existing pattern)
            "temperature_forecast": [15.0] * 48,
        }

    def _extract_price_forecast(self, price_state) -> list[float]:
        """Extract price forecast from entity state.

        For v1, replicate current price across 48 hours.
        Future versions can parse Tibber attributes for actual forecasts.

        Args:
            price_state: Price entity state

        Returns:
            48-hour price forecast array
        """
        try:
            current_price = float(price_state.state)
        except (ValueError, TypeError):
            _LOGGER.warning("Cannot convert price to float, using 0.0")
            current_price = 0.0

        return [current_price] * 48

    def _extract_consumption_forecast(self, consumption_state) -> list[float]:
        """Extract consumption forecast from entity state.

        For v1, replicate current consumption across 48 hours.

        Args:
            consumption_state: Consumption entity state

        Returns:
            48-hour consumption forecast array
        """
        try:
            current_consumption = float(consumption_state.state)
        except (ValueError, TypeError):
            _LOGGER.warning("Cannot convert consumption to float, using default 500.0")
            current_consumption = 500.0  # Reasonable default ~500Wh per hour

        return [current_consumption] * 48

    def _parse_optimization_response(self, response: dict[str, Any]) -> dict[str, Any]:
        """Parse optimization response from EOS server.

        Args:
            response: Raw EOS optimization response

        Returns:
            Structured dict with optimization results

        Raises:
            UpdateFailed: If response is invalid or contains errors
        """
        # Check for error in response
        if "error" in response:
            _LOGGER.error("EOS optimization returned error: %s", response["error"])
            raise UpdateFailed(f"EOS optimization error: {response['error']}")

        # Validate expected keys are present
        required_keys = ["ac_charge", "dc_charge", "discharge_allowed"]
        missing_keys = [key for key in required_keys if key not in response]
        if missing_keys:
            _LOGGER.error("EOS response missing keys: %s", missing_keys)
            raise UpdateFailed(f"Invalid EOS response: missing {missing_keys}")

        return {
            "ac_charge": response.get("ac_charge", []),
            "dc_charge": response.get("dc_charge", []),
            "discharge_allowed": response.get("discharge_allowed", []),
            "start_solution": response.get("start_solution"),
            "raw_response": response,
            "last_update": dt_util.now().isoformat(),
            "last_success": True,
        }

    async def async_shutdown(self) -> None:
        """Clean up coordinator resources."""
        await self.session.close()
