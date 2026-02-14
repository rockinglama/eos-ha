"""DataUpdateCoordinator for EOS HA integration."""
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
    CONF_BIDDING_ZONE,
    CONF_CONSUMPTION_ENTITY,
    CONF_EOS_URL,
    CONF_INVERTER_POWER,
    CONF_MAX_CHARGE_POWER,
    CONF_MAX_SOC,
    CONF_MIN_SOC,
    CONF_PRICE_ENTITY,
    CONF_PRICE_SOURCE,
    CONF_PV_ARRAYS,
    CONF_SOC_ENTITY,
    DEFAULT_BIDDING_ZONE,
    DEFAULT_SCAN_INTERVAL,
    PRICE_SOURCE_AKKUDOKTOR,
    PRICE_SOURCE_ENERGYCHARTS,
    PRICE_SOURCE_EXTERNAL,
    PV_FORECAST_CACHE_HOURS,
)

_LOGGER = logging.getLogger(__name__)


class EOSCoordinator(DataUpdateCoordinator):
    """DataUpdateCoordinator to manage EOS optimization cycle."""

    def __init__(self, hass: HomeAssistant, config_entry) -> None:
        super().__init__(
            hass,
            _LOGGER,
            name="EOS Optimization",
            update_interval=timedelta(seconds=DEFAULT_SCAN_INTERVAL),
        )
        self.config_entry = config_entry
        self.session = aiohttp.ClientSession()
        self._eos_client = EOSApiClient(
            self.session,
            config_entry.data[CONF_EOS_URL],
        )
        self._akkudoktor_client = AkkudoktorApiClient(self.session)

        # PV forecast cache (for fallback/external mode)
        self._pv_forecast_cache: list[float] | None = None
        self._pv_forecast_timestamp = None

        self._first_refresh = True
        self._eos_configured = False

        # Manual override state
        self._override_mode: str | None = None
        self._override_until = None

        # Last used forecasts
        self._last_pv_forecast: list[float] = []
        self._last_consumption_forecast: list[float] = []
        self._last_price_forecast: list[float] = []

        # EOS native data
        self._energy_plan: dict[str, Any] = {}
        self._resource_status: dict[str, Any] = {}

    def _get_config(self, key: str, default=None):
        """Get config value from options (runtime) with data (setup) as fallback."""
        return self.config_entry.options.get(
            key, self.config_entry.data.get(key, default)
        )

    @property
    def eos_client(self) -> EOSApiClient:
        """Expose EOS client for service calls."""
        return self._eos_client

    async def _push_eos_config(self) -> None:
        """Push HA configuration to EOS server at setup time."""
        if self._eos_configured:
            return

        _LOGGER.info("Pushing HA configuration to EOS server")

        # 1. Set location
        lat = self.config_entry.data.get("latitude")
        lon = self.config_entry.data.get("longitude")
        tz = self.hass.config.time_zone
        if lat and lon:
            await self._eos_client.put_config("general", {
                "latitude": lat,
                "longitude": lon,
                "timezone": tz,
            })

        # 2. Configure electricity price provider
        price_source = self._get_config(CONF_PRICE_SOURCE, PRICE_SOURCE_AKKUDOKTOR)
        if price_source == PRICE_SOURCE_AKKUDOKTOR:
            await self._eos_client.put_config("elecprice", {
                "provider": "ElecPriceAkkudoktor",
            })
        elif price_source == PRICE_SOURCE_ENERGYCHARTS:
            bidding_zone = self._get_config(CONF_BIDDING_ZONE, DEFAULT_BIDDING_ZONE)
            await self._eos_client.put_config("elecprice", {
                "provider": "ElecPriceEnergyCharts",
                "energycharts": {"bidding_zone": bidding_zone},
            })
        # external: don't configure EOS elecprice, we'll push prices ourselves

        # 3. Configure PV forecast
        pv_arrays = self._get_config(CONF_PV_ARRAYS) or []
        if pv_arrays:
            planes = []
            for arr in pv_arrays:
                planes.append({
                    "surface_azimuth": arr["azimuth"],
                    "surface_tilt": arr["tilt"],
                    "peakpower": arr["power"] / 1000.0,  # Wp -> kWp
                    "inverter_paco": arr.get("inverter_power", arr["power"]),
                })
            await self._eos_client.put_config("pvforecast", {
                "provider": "PVForecastAkkudoktor",
                "planes": planes,
            })

        self._eos_configured = True
        _LOGGER.info("EOS server configured successfully")

    async def _push_measurements(self) -> None:
        """Push current SOC and consumption to EOS measurement store."""
        soc_entity = self._get_config(CONF_SOC_ENTITY)
        consumption_entity = self._get_config(CONF_CONSUMPTION_ENTITY)
        now_str = dt_util.now().isoformat()

        if soc_entity:
            soc_state = self.hass.states.get(soc_entity)
            if soc_state and soc_state.state not in (STATE_UNAVAILABLE, STATE_UNKNOWN):
                try:
                    soc_val = float(soc_state.state)
                    await self._eos_client.put_measurement_value(now_str, "soc_percentage", soc_val)
                except (ValueError, TypeError):
                    pass

        if consumption_entity:
            cons_state = self.hass.states.get(consumption_entity)
            if cons_state and cons_state.state not in (STATE_UNAVAILABLE, STATE_UNKNOWN):
                try:
                    cons_val = float(cons_state.state)
                    await self._eos_client.put_measurement_value(now_str, "load_wh", cons_val)
                except (ValueError, TypeError):
                    pass

    async def _async_update_data(self) -> dict[str, Any]:
        """Fetch data from HA entities and run optimization cycle."""

        # First refresh: push config and return empty structure
        if self._first_refresh:
            self._first_refresh = False
            _LOGGER.info("First refresh: configuring EOS, scheduling full update")
            try:
                await self._push_eos_config()
            except Exception as err:
                _LOGGER.warning("Failed to push EOS config: %s", err)
            return self._empty_data()

        # Ensure EOS is configured
        if not self._eos_configured:
            try:
                await self._push_eos_config()
            except Exception as err:
                _LOGGER.warning("Failed to push EOS config: %s", err)

        # Push measurements (best effort)
        try:
            await self._push_measurements()
        except Exception as err:
            _LOGGER.debug("Failed to push measurements: %s", err)

        # Fetch EOS native data (best effort)
        try:
            self._energy_plan = await self._eos_client.get_energy_plan()
        except Exception:
            pass

        try:
            self._resource_status = await self._eos_client.get_resource_status("battery1")
        except Exception:
            pass

        # Read HA input entities
        soc_entity = self._get_config(CONF_SOC_ENTITY)
        consumption_entity = self._get_config(CONF_CONSUMPTION_ENTITY)

        soc_state = self.hass.states.get(soc_entity)
        consumption_state = self.hass.states.get(consumption_entity)

        unavailable = []
        if soc_state is None or soc_state.state in (STATE_UNAVAILABLE, STATE_UNKNOWN):
            unavailable.append(f"SOC ({soc_entity})")
        if consumption_state is None or consumption_state.state in (STATE_UNAVAILABLE, STATE_UNKNOWN):
            unavailable.append(f"consumption ({consumption_entity})")

        # Price handling depends on source
        price_source = self._get_config(CONF_PRICE_SOURCE, PRICE_SOURCE_AKKUDOKTOR)
        price_state = None

        if price_source == PRICE_SOURCE_EXTERNAL:
            price_entity = self._get_config(CONF_PRICE_ENTITY)
            price_state = self.hass.states.get(price_entity)
            if price_state is None or price_state.state in (STATE_UNAVAILABLE, STATE_UNKNOWN):
                unavailable.append(f"price ({price_entity})")

        if unavailable:
            _LOGGER.debug("Required entities unavailable: %s", ", ".join(unavailable))
            if self.data:
                return self.data
            raise UpdateFailed(f"Required entities unavailable: {', '.join(unavailable)}")

        # Get PV forecast
        pv_forecast = await self._get_pv_forecast(price_source)
        if pv_forecast is None:
            pv_forecast = [0.0] * 48

        # Get price forecast
        price_forecast = await self._get_price_forecast(price_source, price_state)

        # Build EOS request and optimize
        eos_request = self._build_eos_request(
            price_forecast,
            soc_state,
            consumption_state,
            pv_forecast,
        )

        try:
            current_hour = dt_util.now().hour
            result = await self._eos_client.optimize(eos_request, current_hour)
        except (EOSConnectionError, EOSOptimizationError) as err:
            raise UpdateFailed(str(err)) from err

        return self._parse_optimization_response(result)

    async def _get_pv_forecast(self, price_source: str) -> list[float] | None:
        """Get PV forecast — prefer EOS native, fallback to Akkudoktor API."""
        # Try EOS native pvforecast first
        pv_arrays = self._get_config(CONF_PV_ARRAYS) or []
        if pv_arrays:
            eos_forecast = await self._eos_client.get_pvforecast()
            if eos_forecast:
                self._pv_forecast_cache = eos_forecast
                self._pv_forecast_timestamp = dt_util.now()
                return eos_forecast

        # Fallback to direct Akkudoktor API
        return await self._get_pv_forecast_cached()

    async def _get_price_forecast(self, price_source: str, price_state) -> list[float]:
        """Get price forecast based on configured source."""
        if price_source in (PRICE_SOURCE_AKKUDOKTOR, PRICE_SOURCE_ENERGYCHARTS):
            prices = await self._eos_client.get_strompreis()
            if prices:
                self._last_price_forecast = prices
                return prices
            _LOGGER.warning("EOS strompreis empty, using flat fallback")

        # External or fallback
        if price_state:
            return self._extract_price_forecast(price_state)

        # Last resort
        if self._last_price_forecast:
            return self._last_price_forecast
        return [0.0001] * 48  # ~0.10 EUR/kWh default

    async def _get_pv_forecast_cached(self) -> list[float] | None:
        """Get PV forecast with 6-hour caching from Akkudoktor API."""
        cache_valid = False
        if self._pv_forecast_cache and self._pv_forecast_timestamp:
            age = dt_util.now() - self._pv_forecast_timestamp
            if age < timedelta(hours=PV_FORECAST_CACHE_HOURS):
                cache_valid = True

        if cache_valid:
            return self._pv_forecast_cache

        try:
            lat = self.config_entry.data.get("latitude")
            lon = self.config_entry.data.get("longitude")
            if lat is None or lon is None:
                if self._pv_forecast_cache:
                    return self._pv_forecast_cache
                return None

            pv_arrays = self._get_config(CONF_PV_ARRAYS) or []
            forecast = await self._akkudoktor_client.get_pv_forecast(
                lat=lat, lon=lon,
                pv_arrays=pv_arrays if pv_arrays else None,
                timezone=self.hass.config.time_zone,
            )
            self._pv_forecast_cache = forecast
            self._pv_forecast_timestamp = dt_util.now()
            return forecast
        except AkkudoktorApiError as err:
            _LOGGER.warning("Akkudoktor API error: %s", err)
            if self._pv_forecast_cache:
                return self._pv_forecast_cache
            return None

    def _build_eos_request(
        self,
        price_forecast: list[float],
        soc_state,
        consumption_state,
        pv_forecast: list[float],
    ) -> dict[str, Any]:
        """Build EOS optimization request."""
        consumption_forecast = self._extract_consumption_forecast(consumption_state)

        self._last_pv_forecast = pv_forecast
        self._last_price_forecast = price_forecast
        self._last_consumption_forecast = consumption_forecast

        return {
            "ems": {
                "pv_prognose_wh": pv_forecast,
                "strompreis_euro_pro_wh": price_forecast,
                "einspeiseverguetung_euro_pro_wh": [0.0] * 48,
                "preis_euro_pro_wh_akku": 0.0,
                "gesamtlast": consumption_forecast,
            },
            "pv_akku": {
                "device_id": "battery1",
                "capacity_wh": int(self._get_config(CONF_BATTERY_CAPACITY) * 1000),
                "charging_efficiency": 0.88,
                "discharging_efficiency": 0.88,
                "max_charge_power_w": self._get_config(CONF_MAX_CHARGE_POWER),
                "initial_soc_percentage": round(float(soc_state.state)),
                "min_soc_percentage": self._get_config(CONF_MIN_SOC),
                "max_soc_percentage": self._get_config(CONF_MAX_SOC),
            },
            "inverter": {
                "device_id": "inverter1",
                "max_power_wh": self._get_config(CONF_INVERTER_POWER),
                "battery_id": "battery1",
            },
            "eauto": None,
            "temperature_forecast": [15.0] * 48,
        }

    def _extract_price_forecast(self, price_state) -> list[float]:
        """Extract price forecast from HA entity state."""
        try:
            current_price = float(price_state.state)
        except (ValueError, TypeError):
            current_price = 0.0
        return [current_price] * 48

    def _extract_consumption_forecast(self, consumption_state) -> list[float]:
        """Extract consumption forecast from HA entity state."""
        try:
            current_consumption = float(consumption_state.state)
        except (ValueError, TypeError):
            current_consumption = 500.0
        return [current_consumption] * 48

    def _parse_optimization_response(self, response: dict[str, Any]) -> dict[str, Any]:
        """Parse optimization response from EOS server."""
        if "error" in response:
            raise UpdateFailed(f"EOS optimization error: {response['error']}")

        required_keys = ["ac_charge", "dc_charge", "discharge_allowed"]
        missing_keys = [key for key in required_keys if key not in response]
        if missing_keys:
            raise UpdateFailed(f"Invalid EOS response: missing {missing_keys}")

        result = response.get("result", {})

        return {
            "ac_charge": response.get("ac_charge", []),
            "dc_charge": response.get("dc_charge", []),
            "discharge_allowed": response.get("discharge_allowed", []),
            "start_solution": response.get("start_solution"),
            "battery_soc_forecast": result.get("akku_soc_pro_stunde", []),
            "cost_per_hour": result.get("Kosten_Euro_pro_Stunde", []),
            "revenue_per_hour": result.get("Einnahmen_Euro_pro_Stunde", []),
            "grid_consumption_per_hour": result.get("Netzbezug_Wh_pro_Stunde", []),
            "grid_feedin_per_hour": result.get("Netzeinspeisung_Wh_pro_Stunde", []),
            "load_per_hour": result.get("Last_Wh_pro_Stunde", []),
            "losses_per_hour": result.get("Verluste_Pro_Stunde", []),
            "total_balance": result.get("Gesamtbilanz_Euro"),
            "total_cost": result.get("Gesamtkosten_Euro"),
            "total_revenue": result.get("Gesamteinnahmen_Euro"),
            "total_losses": result.get("Gesamt_Verluste"),
            "electricity_price": result.get("Electricity_price", []),
            "pv_forecast": self._last_pv_forecast,
            "consumption_forecast": self._last_consumption_forecast,
            "price_forecast": self._last_price_forecast,
            "active_override": self.active_override,
            "energy_plan": self._energy_plan,
            "resource_status": self._resource_status,
            "raw_response": response,
            "last_update": dt_util.now().isoformat(),
            "last_success": True,
        }

    def _empty_data(self) -> dict[str, Any]:
        """Return empty data structure for first refresh."""
        return {
            "ac_charge": [],
            "dc_charge": [],
            "discharge_allowed": [],
            "start_solution": None,
            "battery_soc_forecast": [],
            "cost_per_hour": [],
            "revenue_per_hour": [],
            "grid_consumption_per_hour": [],
            "grid_feedin_per_hour": [],
            "load_per_hour": [],
            "losses_per_hour": [],
            "gesamtkosten_euro": None,
            "gesamteinnahmen_euro": None,
            "gesamtbilanz_euro": None,
            "total_losses": None,
            "electricity_price": [],
            "pv_forecast": [],
            "consumption_forecast": [],
            "price_forecast": [],
            "energy_plan": {},
            "resource_status": {},
            "raw_response": {},
            "last_update": dt_util.now().isoformat(),
            "last_success": False,
        }

    def set_override(self, mode: str, duration_minutes: int) -> None:
        """Set manual override mode."""
        if mode == "auto":
            self._override_mode = None
            self._override_until = None
        else:
            self._override_mode = mode
            self._override_until = dt_util.now() + timedelta(minutes=duration_minutes)

    @property
    def active_override(self) -> str | None:
        """Return active override mode or None if expired/not set."""
        if self._override_mode and self._override_until:
            if dt_util.now() < self._override_until:
                return self._override_mode
            self._override_mode = None
            self._override_until = None
        return None

    async def async_shutdown(self) -> None:
        """Clean up coordinator resources."""
        await self.session.close()
