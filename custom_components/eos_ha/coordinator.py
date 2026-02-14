"""DataUpdateCoordinator for EOS HA integration — auto-optimization mode."""
from __future__ import annotations

from datetime import timedelta
import logging
from typing import Any

import aiohttp

from homeassistant.const import STATE_UNAVAILABLE, STATE_UNKNOWN
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util

from .api import EOSApiClient, EOSConnectionError
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
    DEFAULT_BIDDING_ZONE,
    DEFAULT_EV_CAPACITY,
    DEFAULT_EV_CHARGE_POWER,
    DEFAULT_EV_EFFICIENCY,
    DEFAULT_FEED_IN_TARIFF,
    DEFAULT_SCAN_INTERVAL,
    PRICE_SOURCE_AKKUDOKTOR,
    PRICE_SOURCE_ENERGYCHARTS,
    PRICE_SOURCE_EXTERNAL,
)

_LOGGER = logging.getLogger(__name__)


class EOSCoordinator(DataUpdateCoordinator):
    """DataUpdateCoordinator to manage EOS auto-optimization cycle."""

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

        self._first_refresh = True
        self._eos_configured = False

        # Manual override state
        self._override_mode: str | None = None
        self._override_until = None

        # Availability tracking
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
        """Push full HA configuration to EOS server: location, providers, devices, EMS mode."""
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
        # external: we'll push prices via import_prediction

        # 3. Configure PV forecast
        pv_arrays = self._get_config(CONF_PV_ARRAYS) or []
        if pv_arrays:
            planes = []
            for arr in pv_arrays:
                planes.append({
                    "surface_azimuth": arr["azimuth"],
                    "surface_tilt": arr["tilt"],
                    "peakpower": arr["power"] / 1000.0,
                    "inverter_paco": arr.get("inverter_power", arr["power"]),
                })
            await self._eos_client.put_config("pvforecast", {
                "provider": "PVForecastAkkudoktor",
                "planes": planes,
            })

        # 4. Configure feed-in tariff
        feed_in_tariff = self._get_config(CONF_FEED_IN_TARIFF, DEFAULT_FEED_IN_TARIFF)
        if feed_in_tariff:
            await self._eos_client.put_config("feedintariff/provider", "FeedInTariffFixed")
            await self._eos_client.put_config(
                "feedintariff/provider_settings/FeedInTariffFixed/feed_in_tariff_kwh",
                feed_in_tariff,
            )

        # 5. Configure load provider
        await self._eos_client.put_config("load", {
            "provider": "LoadAkkudoktor",
        })

        # 6. Configure devices (battery, inverter, EV, appliances)
        await self._push_device_config()

        # 7. Enable auto-optimization
        await self._eos_client.put_config("ems", {
            "mode": "OPTIMIZATION",
            "interval": 3600,
        })

        self._eos_configured = True
        _LOGGER.info("EOS server configured with auto-optimization enabled")

    async def _push_device_config(self) -> None:
        """Configure EOS devices: battery, inverter, EV, appliances."""
        soc_entity = self._get_config(CONF_SOC_ENTITY)
        initial_soc = 50
        if soc_entity:
            soc_state = self.hass.states.get(soc_entity)
            if soc_state and soc_state.state not in (STATE_UNAVAILABLE, STATE_UNKNOWN):
                try:
                    initial_soc = round(float(soc_state.state))
                except (ValueError, TypeError):
                    pass

        devices: dict[str, Any] = {
            "batteries": [{
                "device_id": "battery1",
                "capacity_wh": int(self._get_config(CONF_BATTERY_CAPACITY) * 1000),
                "charging_efficiency": 0.88,
                "discharging_efficiency": 0.88,
                "max_charge_power_w": self._get_config(CONF_MAX_CHARGE_POWER),
                "initial_soc_percentage": initial_soc,
                "min_soc_percentage": self._get_config(CONF_MIN_SOC),
                "max_soc_percentage": self._get_config(CONF_MAX_SOC),
            }],
            "inverters": [{
                "device_id": "inverter1",
                "max_power_wh": self._get_config(CONF_INVERTER_POWER),
                "battery_id": "battery1",
            }],
        }

        # EV
        if self._get_config(CONF_EV_ENABLED, False):
            ev_soc = 50
            ev_soc_entity = self._get_config(CONF_EV_SOC_ENTITY)
            if ev_soc_entity:
                ev_state = self.hass.states.get(ev_soc_entity)
                if ev_state and ev_state.state not in (STATE_UNAVAILABLE, STATE_UNKNOWN):
                    try:
                        ev_soc = round(float(ev_state.state))
                    except (ValueError, TypeError):
                        pass

            devices["electric_vehicles"] = [{
                "device_id": "ev1",
                "capacity_wh": int(self._get_config(CONF_EV_CAPACITY, DEFAULT_EV_CAPACITY) * 1000),
                "charging_efficiency": self._get_config(CONF_EV_EFFICIENCY, DEFAULT_EV_EFFICIENCY),
                "initial_soc_percentage": ev_soc,
                "min_soc_percentage": 10,
                "max_soc_percentage": 100,
                "max_charge_power_w": int(self._get_config(CONF_EV_CHARGE_POWER, DEFAULT_EV_CHARGE_POWER)),
            }]

        # Appliances
        appliances = self._get_config(CONF_APPLIANCES) or []
        if appliances:
            devices["home_appliances"] = [
                {
                    "device_id": app.get("device_id", app["name"].lower().replace(" ", "_")),
                    "consumption_wh": app["consumption_wh"],
                    "duration_h": app["duration_h"],
                }
                for app in appliances
            ]

        await self._eos_client.put_config("devices", devices)

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

            series = []
            for stat in entity_stats:
                val = stat.get("mean") or stat.get("sum")
                if val is not None:
                    series.append({
                        "datetime": stat["start"].isoformat() if hasattr(stat["start"], "isoformat") else stat["start"],
                        "load_wh": float(val),
                    })

            if series:
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

    async def _push_external_prices(self) -> None:
        """Push Tibber/external prices to EOS via prediction import if configured."""
        price_source = self._get_config(CONF_PRICE_SOURCE, PRICE_SOURCE_AKKUDOKTOR)
        if price_source != PRICE_SOURCE_EXTERNAL:
            return

        price_entity = self._get_config(CONF_PRICE_ENTITY)
        if not price_entity:
            return

        price_state = self.hass.states.get(price_entity)
        if not price_state or price_state.state in (STATE_UNAVAILABLE, STATE_UNKNOWN):
            return

        # Try Tibber-style forecast attribute
        forecast = price_state.attributes.get("forecast")
        if forecast and isinstance(forecast, list):
            try:
                price_data = {}
                for entry in forecast:
                    start = entry.get("start")
                    total = entry.get("total")
                    if start and total is not None:
                        # Tibber prices are EUR/kWh — EOS ElecPriceImport expects EUR/kWh
                        price_data[str(start)] = float(total)

                if price_data:
                    await self._eos_client.import_prediction(
                        "ElecPriceImport",
                        price_data,
                        force_enable=True,
                    )
                    _LOGGER.debug("Pushed %d external price points to EOS", len(price_data))
                    return
            except Exception as err:
                _LOGGER.debug("Error pushing Tibber prices: %s", err)

        # Fallback: single current price — not very useful but push anyway
        try:
            current_price = float(price_state.state)
            now = dt_util.now().replace(minute=0, second=0, microsecond=0)
            price_data = {}
            for h in range(48):
                ts = (now + timedelta(hours=h)).isoformat()
                price_data[ts] = current_price
            await self._eos_client.import_prediction(
                "ElecPriceImport", price_data, force_enable=True,
            )
        except (ValueError, TypeError):
            pass

    async def _async_update_data(self) -> dict[str, Any]:
        """Fetch optimization solution and predictions from EOS."""

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

        # Push external prices if applicable (best effort)
        try:
            await self._push_external_prices()
        except Exception as err:
            _LOGGER.debug("Failed to push external prices: %s", err)

        # Fetch EOS native data (best effort)
        try:
            self._energy_plan = await self._eos_client.get_energy_plan()
        except Exception:
            pass

        try:
            self._resource_status = await self._eos_client.get_resource_status("battery1")
        except Exception:
            pass

        # Fetch optimization solution
        try:
            solution = await self._eos_client.get_optimization_solution()
        except EOSConnectionError as err:
            if self._last_available is not False:
                _LOGGER.error("EOS server is unavailable: %s", err)
                self._last_available = False
            if self.data:
                return self.data
            raise UpdateFailed(str(err)) from err

        if not solution:
            if self._last_available is not False:
                _LOGGER.warning("No optimization solution available from EOS")
                self._last_available = False
            if self.data:
                return self.data
            return self._empty_data()

        if self._last_available is not True:
            if self._last_available is False:
                _LOGGER.info("EOS server connection restored")
            self._last_available = True

        # Fetch prediction series for forecasts
        pv_forecast = await self._fetch_prediction_list("pvforecast_ac_power")
        price_forecast = await self._fetch_prediction_list("elecprice_marketprice_kwh")
        consumption_forecast = await self._fetch_prediction_list("loadakkudoktor_mean_power_w")

        return self._parse_optimization_solution(
            solution, pv_forecast, price_forecast, consumption_forecast
        )

    async def _fetch_prediction_list(self, key: str) -> list[float]:
        """Fetch a prediction series and return as ordered list of values."""
        try:
            result = await self._eos_client.get_prediction_series(key)
            data = result.get("data", {})
            if not data:
                return []
            # Data is {datetime_str: value} — sort by key and return values
            sorted_items = sorted(data.items())
            return [float(v) for _, v in sorted_items]
        except Exception as err:
            _LOGGER.debug("Error fetching prediction series %s: %s", key, err)
            return []

    def _parse_optimization_solution(
        self,
        solution: dict[str, Any],
        pv_forecast: list[float],
        price_forecast: list[float],
        consumption_forecast: list[float],
    ) -> dict[str, Any]:
        """Parse the EOS optimization solution into the data format sensors expect."""
        sol_data = solution.get("solution", {}).get("data", {})
        pred_data = solution.get("prediction", {}).get("data", {})

        # Sort solution entries by datetime
        sorted_sol = sorted(sol_data.items())

        # Extract arrays from solution
        ac_charge = []
        dc_charge = []
        discharge_allowed = []
        battery_soc_forecast = []
        cost_per_hour = []
        revenue_per_hour = []
        grid_consumption_per_hour = []
        grid_feedin_per_hour = []
        load_per_hour = []
        losses_per_hour = []

        for _, entry in sorted_sol:
            ac_charge.append(entry.get("genetic_ac_charge_factor", 0.0))
            dc_charge.append(entry.get("genetic_dc_charge_factor", 0.0))
            discharge_allowed.append(entry.get("genetic_discharge_allowed_factor", True))
            # SOC is a factor 0-1, convert to percentage
            battery_soc_forecast.append(
                round(entry.get("battery1_soc_factor", 0.0) * 100, 2)
            )
            cost_per_hour.append(entry.get("costs_amt", 0.0))
            revenue_per_hour.append(entry.get("revenue_amt", 0.0))
            grid_consumption_per_hour.append(entry.get("grid_consumption_energy_wh", 0.0))
            grid_feedin_per_hour.append(entry.get("grid_feedin_energy_wh", 0.0))
            load_per_hour.append(entry.get("load_energy_wh", 0.0))
            losses_per_hour.append(entry.get("losses_energy_wh", 0.0))

        # Extract PV forecast from prediction data if not from series
        if not pv_forecast and pred_data:
            sorted_pred = sorted(pred_data.items())
            pv_forecast = [
                e.get("pvforecast_ac_energy_wh", 0.0) for _, e in sorted_pred
            ]

        # Extract price forecast from prediction data (EUR/kWh → EUR/Wh)
        if not price_forecast and pred_data:
            sorted_pred = sorted(pred_data.items())
            price_forecast = [
                e.get("elec_price_amt_kwh", 0.0) / 1000.0 for _, e in sorted_pred
            ]
        elif price_forecast:
            # Series returns EUR/kWh, convert to EUR/Wh for backward compat
            price_forecast = [p / 1000.0 for p in price_forecast]

        # Totals from solution metadata
        total_cost = solution.get("total_costs_amt")
        total_revenue = solution.get("total_revenues_amt")
        total_losses = solution.get("total_losses_energy_wh")
        total_balance = None
        if total_cost is not None and total_revenue is not None:
            total_balance = total_revenue - total_cost

        return {
            "ac_charge": ac_charge,
            "dc_charge": dc_charge,
            "discharge_allowed": discharge_allowed,
            "start_solution": solution.get("valid_from"),
            "battery_soc_forecast": battery_soc_forecast,
            "cost_per_hour": cost_per_hour,
            "revenue_per_hour": revenue_per_hour,
            "grid_consumption_per_hour": grid_consumption_per_hour,
            "grid_feedin_per_hour": grid_feedin_per_hour,
            "load_per_hour": load_per_hour,
            "losses_per_hour": losses_per_hour,
            "total_balance": total_balance,
            "total_cost": total_cost,
            "total_revenue": total_revenue,
            "total_losses": total_losses,
            "electricity_price": price_forecast,
            "pv_forecast": pv_forecast,
            "consumption_forecast": consumption_forecast,
            "price_forecast": price_forecast,
            "active_override": self.active_override,
            "energy_plan": self._energy_plan,
            "resource_status": self._resource_status,
            "ev_charge_plan": {},
            "appliance_schedules": {},
            "raw_response": solution,
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
            "total_balance": None,
            "total_cost": None,
            "total_revenue": None,
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
            self._sg_ready_override_until = None
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
