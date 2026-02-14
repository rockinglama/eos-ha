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
    CONF_APPLIANCES,
    CONF_BATTERY_CAPACITY,
    CONF_BIDDING_ZONE,
    CONF_CONSUMPTION_ENTITY,
    CONF_EOS_URL,
    CONF_EV_CAPACITY,
    CONF_EV_CHARGE_POWER,
    CONF_EV_EFFICIENCY,
    CONF_EV_ENABLED,
    CONF_EV_SOC_ENTITY,
    CONF_FEED_IN_TARIFF,
    CONF_INVERTER_POWER,
    CONF_MAX_CHARGE_POWER,
    CONF_MAX_SOC,
    CONF_MIN_SOC,
    CONF_PRICE_ENTITY,
    CONF_PRICE_SOURCE,
    CONF_PV_ARRAYS,
    CONF_SOC_ENTITY,
    CONF_TEMPERATURE_ENTITY,
    DEFAULT_BIDDING_ZONE,
    DEFAULT_EV_CAPACITY,
    DEFAULT_EV_CHARGE_POWER,
    DEFAULT_EV_EFFICIENCY,
    DEFAULT_FEED_IN_TARIFF,
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

        # Availability tracking (log-when-unavailable)
        self._last_available: bool | None = None

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

        # 4. Configure feed-in tariff
        feed_in_tariff = self._get_config(CONF_FEED_IN_TARIFF, DEFAULT_FEED_IN_TARIFF)
        if feed_in_tariff:
            await self._eos_client.put_config("feedintariff", {
                "provider": "FeedInTariffFixed",
                "feed_in_tariff_eur_per_kwh": feed_in_tariff,
            })

        # 5. Configure load provider for history-based load
        await self._eos_client.put_config("load", {
            "provider": "LoadAkkudoktor",
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

    async def _push_load_history(self) -> None:
        """Push 7-day consumption history from HA recorder to EOS as measurement series."""
        consumption_entity = self._get_config(CONF_CONSUMPTION_ENTITY)
        if not consumption_entity:
            return

        try:
            from homeassistant.components.recorder import get_instance
            from homeassistant.components.recorder.statistics import (
                statistics_during_period,
            )

            now = dt_util.now()
            start = now - timedelta(days=7)

            stats = await get_instance(self.hass).async_add_executor_job(
                statistics_during_period,
                self.hass,
                start,
                now,
                {consumption_entity},
                "hour",
                None,
                {"mean", "sum"},
            )

            entity_stats = stats.get(consumption_entity, [])
            if not entity_stats:
                _LOGGER.debug("No history stats for %s, skipping load history push", consumption_entity)
                return

            # Build measurement series: list of {datetime, load_wh}
            series = []
            for stat in entity_stats:
                val = stat.get("mean") or stat.get("sum")
                if val is not None:
                    series.append({
                        "datetime": stat["start"].isoformat() if hasattr(stat["start"], "isoformat") else stat["start"],
                        "load_wh": float(val),
                    })

            if series:
                # Push via PUT /v1/measurement/series
                url = f"{self._eos_client.base_url}/v1/measurement/series"
                try:
                    timeout = aiohttp.ClientTimeout(total=15)
                    async with self.session.put(
                        url, json=series, timeout=timeout,
                        headers={"Content-Type": "application/json"},
                    ) as resp:
                        if resp.status == 200:
                            _LOGGER.debug("Pushed %d load history points to EOS", len(series))
                        else:
                            body = await resp.text()
                            _LOGGER.debug("Load history push returned %s: %s", resp.status, body[:200])
                except Exception as err:
                    _LOGGER.debug("Failed to push load history: %s", err)

        except ImportError:
            _LOGGER.debug("Recorder not available, skipping load history")
        except Exception as err:
            _LOGGER.debug("Error fetching load history: %s", err)

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

        # Push load history (best effort)
        try:
            await self._push_load_history()
        except Exception as err:
            _LOGGER.debug("Failed to push load history: %s", err)

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
            if self._last_available is not False:
                _LOGGER.error("EOS server is unavailable: %s", err)
                self._last_available = False
            raise UpdateFailed(str(err)) from err

        if self._last_available is not True:
            if self._last_available is False:
                _LOGGER.info("EOS server connection restored")
            self._last_available = True

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
                "einspeiseverguetung_euro_pro_wh": [self._get_config(CONF_FEED_IN_TARIFF, DEFAULT_FEED_IN_TARIFF) / 1000.0] * 48,
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
            "eauto": self._build_ev_params(soc_state),
            "home_appliances": self._build_appliances_params(),
            "temperature_forecast": self._get_temperature_forecast(),
        }

    def _get_temperature_forecast(self) -> list[float]:
        """Get temperature forecast from configured entity, fallback to 15°C."""
        temp_entity_id = self._get_config(CONF_TEMPERATURE_ENTITY)
        if not temp_entity_id:
            return [15.0] * 48

        state = self.hass.states.get(temp_entity_id)
        if state is None or state.state in (STATE_UNAVAILABLE, STATE_UNKNOWN):
            _LOGGER.debug("Temperature entity %s unavailable, using 15°C fallback", temp_entity_id)
            return [15.0] * 48

        # Check if it's a weather entity with forecast attribute
        forecast = state.attributes.get("forecast")
        if forecast and isinstance(forecast, list):
            try:
                temps = []
                for entry in forecast:
                    temp = entry.get("temperature")
                    if temp is not None:
                        temps.append(float(temp))
                    if len(temps) >= 48:
                        break
                if temps:
                    # Pad to 48 hours if needed
                    while len(temps) < 48:
                        temps.append(temps[-1])
                    return temps[:48]
            except (ValueError, TypeError) as err:
                _LOGGER.debug("Error parsing weather forecast: %s", err)

        # Simple temperature sensor — use current value for all 48h
        try:
            current_temp = float(state.state)
            return [current_temp] * 48
        except (ValueError, TypeError):
            _LOGGER.debug("Cannot parse temperature from %s, using 15°C fallback", temp_entity_id)
            return [15.0] * 48

    def _build_ev_params(self, soc_state) -> dict[str, Any] | None:
        """Build EV parameters if enabled."""
        if not self._get_config(CONF_EV_ENABLED, False):
            return None

        # Get EV SOC from entity or default to 50%
        ev_soc = 50
        ev_soc_entity = self._get_config(CONF_EV_SOC_ENTITY)
        if ev_soc_entity:
            ev_soc_state = self.hass.states.get(ev_soc_entity)
            if ev_soc_state and ev_soc_state.state not in (STATE_UNAVAILABLE, STATE_UNKNOWN):
                try:
                    ev_soc = round(float(ev_soc_state.state))
                except (ValueError, TypeError):
                    pass

        return {
            "device_id": "ev1",
            "capacity_wh": int(self._get_config(CONF_EV_CAPACITY, DEFAULT_EV_CAPACITY) * 1000),
            "charging_efficiency": self._get_config(CONF_EV_EFFICIENCY, DEFAULT_EV_EFFICIENCY),
            "initial_soc_percentage": ev_soc,
            "min_soc_percentage": 10,
            "max_soc_percentage": 100,
            "max_charge_power_w": int(self._get_config(CONF_EV_CHARGE_POWER, DEFAULT_EV_CHARGE_POWER)),
        }

    def _build_appliances_params(self) -> list[dict[str, Any]] | None:
        """Build home appliances parameters."""
        appliances = self._get_config(CONF_APPLIANCES) or []
        if not appliances:
            return None

        return [
            {
                "device_id": app.get("device_id", app["name"].lower().replace(" ", "_")),
                "consumption_wh": app["consumption_wh"],
                "duration_h": app["duration_h"],
            }
            for app in appliances
        ]

    def _extract_price_forecast(self, price_state) -> list[float]:
        """Extract price forecast from HA entity state. Supports Tibber forecast attribute."""
        # Check for Tibber-style forecast attribute
        forecast = price_state.attributes.get("forecast") if price_state else None
        if forecast and isinstance(forecast, list):
            try:
                now = dt_util.now()
                current_hour = now.replace(minute=0, second=0, microsecond=0)
                price_map = {}
                for entry in forecast:
                    start = entry.get("start")
                    total = entry.get("total")
                    if start and total is not None:
                        if isinstance(start, str):
                            entry_time = dt_util.parse_datetime(start)
                        else:
                            entry_time = start
                        if entry_time:
                            # Convert to hour offset from current hour
                            delta = entry_time - current_hour
                            hour_idx = int(delta.total_seconds() / 3600)
                            if 0 <= hour_idx < 48:
                                # Tibber prices are EUR/kWh, EOS needs EUR/Wh
                                price_map[hour_idx] = float(total) / 1000.0

                if price_map:
                    # Fill 48h array, using last known price for gaps
                    result = [0.0] * 48
                    last_price = list(price_map.values())[0] if price_map else 0.0
                    for i in range(48):
                        if i in price_map:
                            last_price = price_map[i]
                        result[i] = last_price
                    _LOGGER.debug("Parsed Tibber forecast: %d prices mapped", len(price_map))
                    return result
            except Exception as err:
                _LOGGER.debug("Error parsing Tibber forecast: %s", err)

        # Fallback: flat current price
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
            "ev_charge_plan": result.get("eauto_obj", result.get("eauto", {})),
            "appliance_schedules": result.get("home_appliances", {}),
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
            "ev_charge_plan": {},
            "appliance_schedules": {},
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

    def set_sg_ready_override(self, mode: int, duration_minutes: int) -> None:
        """Set manual SG-Ready mode override."""
        if duration_minutes == 0:
            self._sg_ready_override_mode = mode
            self._sg_ready_override_until = None  # permanent until next optimization
        else:
            self._sg_ready_override_mode = mode
            self._sg_ready_override_until = dt_util.now() + timedelta(minutes=duration_minutes)

    @property
    def sg_ready_override(self) -> int | None:
        """Return active SG-Ready override mode or None if expired/not set."""
        mode = getattr(self, "_sg_ready_override_mode", None)
        until = getattr(self, "_sg_ready_override_until", None)
        if mode is None:
            return None
        if until is not None and dt_util.now() >= until:
            self._sg_ready_override_mode = None
            self._sg_ready_override_until = None
            return None
        return mode

    def clear_sg_ready_override(self) -> None:
        """Clear SG-Ready override."""
        self._sg_ready_override_mode = None
        self._sg_ready_override_until = None

    async def async_shutdown(self) -> None:
        """Clean up coordinator resources."""
        await self.session.close()
