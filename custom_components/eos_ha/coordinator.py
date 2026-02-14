"""DataUpdateCoordinator for EOS HA integration — HA Adapter mode."""
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
    CONF_GRID_EXPORT_EMR_ENTITY,
    CONF_GRID_IMPORT_EMR_ENTITY,
    CONF_INVERTER_POWER,
    CONF_LOAD_EMR_ENTITY,
    CONF_MAX_CHARGE_POWER,
    CONF_MAX_SOC,
    CONF_MIN_SOC,
    CONF_PRICE_ENTITY,
    CONF_PRICE_SOURCE,
    CONF_PV_ARRAYS,
    CONF_PV_PRODUCTION_EMR_ENTITY,
    CONF_SOC_ENTITY,
    DEFAULT_BIDDING_ZONE,
    DEFAULT_EV_CAPACITY,
    DEFAULT_EV_CHARGE_POWER,
    DEFAULT_EV_EFFICIENCY,
    DEFAULT_FEED_IN_TARIFF,
    DEFAULT_SCAN_INTERVAL,
    EOS_ENTITY_AC_CHARGE,
    EOS_ENTITY_BATTERY_SOC,
    EOS_ENTITY_BATTERY1,
    EOS_ENTITY_COSTS,
    EOS_ENTITY_DATETIME,
    EOS_ENTITY_DC_CHARGE,
    EOS_ENTITY_DISCHARGE_ALLOWED,
    EOS_ENTITY_GRID_CONSUMPTION,
    EOS_ENTITY_GRID_FEEDIN,
    EOS_ENTITY_LOAD,
    EOS_ENTITY_LOSSES,
    EOS_ENTITY_REVENUE,
    PRICE_SOURCE_AKKUDOKTOR,
    PRICE_SOURCE_ENERGYCHARTS,
    PRICE_SOURCE_EXTERNAL,
)

_LOGGER = logging.getLogger(__name__)


def _read_eos_entity(hass, entity_id: str) -> float | None:
    """Read a numeric value from an EOS-created HA entity."""
    state = hass.states.get(entity_id)
    if state is None or state.state in (STATE_UNAVAILABLE, STATE_UNKNOWN):
        return None
    try:
        return float(state.state)
    except (ValueError, TypeError):
        return None


class EOSCoordinator(DataUpdateCoordinator):
    """DataUpdateCoordinator — configures EOS adapter, reads EOS entities + solution."""

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
        """Push full HA configuration to EOS server: location, providers, devices, adapter, EMS mode."""
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

        # 7. Configure HA Adapter — tell EOS which entities to read/write
        await self._push_adapter_config()

        # 8. Enable auto-optimization
        await self._eos_client.put_config("ems", {
            "mode": "OPTIMIZATION",
            "interval": 3600,
        })

        self._eos_configured = True
        _LOGGER.info("EOS server configured with HA adapter and auto-optimization enabled")

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
            app_list = []
            for app in appliances:
                app_cfg: dict[str, Any] = {
                    "device_id": app.get("device_id", app["name"].lower().replace(" ", "_")),
                    "consumption_wh": app["consumption_wh"],
                    "duration_h": app["duration_h"],
                }
                # Time window support
                w_start = app.get("window_start")
                w_end = app.get("window_end")
                if w_start and w_end:
                    # Calculate duration from start to end
                    from datetime import datetime
                    t_start = datetime.strptime(w_start, "%H:%M")
                    t_end = datetime.strptime(w_end, "%H:%M")
                    delta = t_end - t_start
                    if delta.total_seconds() <= 0:
                        delta += timedelta(days=1)  # overnight window
                    hours = int(delta.total_seconds() // 3600)
                    minutes = int((delta.total_seconds() % 3600) // 60)
                    app_cfg["time_windows"] = {
                        "windows": [{
                            "start_time": w_start,
                            "duration": f"PT{hours}H{minutes}M" if minutes else f"PT{hours}H",
                        }]
                    }
                app_list.append(app_cfg)
            devices["home_appliances"] = app_list

        await self._eos_client.put_config("devices", devices)

    async def _push_adapter_config(self) -> None:
        """Configure EOS HA Adapter with entity mappings so EOS reads from / writes to HA."""
        # Build homeassistant config with entity mappings
        ha_config: dict[str, Any] = {
            "config_entity_ids": None,
            "load_emr_entity_ids": None,
            "grid_export_emr_entity_ids": None,
            "grid_import_emr_entity_ids": None,
            "pv_production_emr_entity_ids": None,
            "device_measurement_entity_ids": None,
            "device_instruction_entity_ids": None,
            "solution_entity_ids": None,
        }

        # Device measurements (SOC → EOS reads directly from HA)
        soc_entity = self._get_config(CONF_SOC_ENTITY)
        if soc_entity:
            ha_config["device_measurement_entity_ids"] = {
                "battery1/initial_soc_percentage": soc_entity,
            }

        # Energy meter entities (optional)
        load_emr = self._get_config(CONF_LOAD_EMR_ENTITY)
        if load_emr:
            ha_config["load_emr_entity_ids"] = [load_emr]

        grid_import = self._get_config(CONF_GRID_IMPORT_EMR_ENTITY)
        if grid_import:
            ha_config["grid_import_emr_entity_ids"] = [grid_import]

        grid_export = self._get_config(CONF_GRID_EXPORT_EMR_ENTITY)
        if grid_export:
            ha_config["grid_export_emr_entity_ids"] = [grid_export]

        pv_production = self._get_config(CONF_PV_PRODUCTION_EMR_ENTITY)
        if pv_production:
            ha_config["pv_production_emr_entity_ids"] = [pv_production]

        # Enable the adapter provider first (must be a list)
        await self._eos_client.set_adapter_provider("HomeAssistant")

        # Set individual adapter sub-keys (bulk PUT on /adapter fails)
        for key, value in ha_config.items():
            if value is not None:
                await self._eos_client.put_config(f"adapter/homeassistant/{key}", value)
        _LOGGER.info("EOS HA adapter configured with entity mappings")

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

        # Fallback: single current price
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
        """Read EOS entities from HA + fetch full solution for forecast arrays."""

        # First refresh: push config and return empty structure
        if self._first_refresh:
            self._first_refresh = False
            _LOGGER.info("First refresh: configuring EOS with HA adapter")
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

        # Push external prices if applicable (best effort)
        try:
            await self._push_external_prices()
        except Exception as err:
            _LOGGER.debug("Failed to push external prices: %s", err)

        # Read current values from EOS-created HA entities
        current_ac_charge = _read_eos_entity(self.hass, EOS_ENTITY_AC_CHARGE)
        current_dc_charge = _read_eos_entity(self.hass, EOS_ENTITY_DC_CHARGE)
        current_discharge = _read_eos_entity(self.hass, EOS_ENTITY_DISCHARGE_ALLOWED)
        current_soc = _read_eos_entity(self.hass, EOS_ENTITY_BATTERY_SOC)
        current_cost = _read_eos_entity(self.hass, EOS_ENTITY_COSTS)
        current_revenue = _read_eos_entity(self.hass, EOS_ENTITY_REVENUE)
        current_grid_consumption = _read_eos_entity(self.hass, EOS_ENTITY_GRID_CONSUMPTION)
        current_grid_feedin = _read_eos_entity(self.hass, EOS_ENTITY_GRID_FEEDIN)
        current_load = _read_eos_entity(self.hass, EOS_ENTITY_LOAD)
        current_losses = _read_eos_entity(self.hass, EOS_ENTITY_LOSSES)

        # Check if EOS entities exist (adapter is working)
        eos_entities_available = current_ac_charge is not None or current_soc is not None

        # Fetch full solution from API for forecast arrays (48h timeseries)
        solution = {}
        try:
            solution = await self._eos_client.get_optimization_solution()
        except EOSConnectionError as err:
            if self._last_available is not False:
                _LOGGER.error("EOS server is unavailable: %s", err)
                self._last_available = False
            if not eos_entities_available:
                if self.data:
                    return self.data
                raise UpdateFailed(str(err)) from err
        except Exception as err:
            _LOGGER.debug("Error fetching solution: %s", err)

        if not solution and not eos_entities_available:
            if self._last_available is not False:
                _LOGGER.warning("No optimization solution and no EOS entities available")
                self._last_available = False
            if self.data:
                return self.data
            return self._empty_data()

        if self._last_available is not True:
            if self._last_available is False:
                _LOGGER.info("EOS data available again")
            self._last_available = True

        # Parse full solution for forecast arrays
        ac_charge_arr = []
        dc_charge_arr = []
        discharge_arr = []
        soc_arr = []
        cost_arr = []
        revenue_arr = []
        grid_consumption_arr = []
        grid_feedin_arr = []
        load_arr = []
        losses_arr = []
        pv_forecast = []
        price_forecast = []
        consumption_forecast = []

        total_cost = None
        total_revenue = None
        total_losses = None
        valid_from = None

        if solution:
            sol_data = solution.get("solution", {}).get("data", {})
            pred_data = solution.get("prediction", {}).get("data", {})
            sorted_sol = sorted(sol_data.items()) if sol_data else []

            for _, entry in sorted_sol:
                ac_charge_arr.append(entry.get("genetic_ac_charge_factor", 0.0))
                dc_charge_arr.append(entry.get("genetic_dc_charge_factor", 0.0))
                discharge_arr.append(entry.get("genetic_discharge_allowed_factor", True))
                soc_arr.append(round(entry.get("battery1_soc_factor", 0.0) * 100, 2))
                cost_arr.append(entry.get("costs_amt", 0.0))
                revenue_arr.append(entry.get("revenue_amt", 0.0))
                grid_consumption_arr.append(entry.get("grid_consumption_energy_wh", 0.0))
                grid_feedin_arr.append(entry.get("grid_feedin_energy_wh", 0.0))
                load_arr.append(entry.get("load_energy_wh", 0.0))
                losses_arr.append(entry.get("losses_energy_wh", 0.0))

            if pred_data:
                sorted_pred = sorted(pred_data.items())
                pv_forecast = [e.get("pvforecast_ac_energy_wh", 0.0) for _, e in sorted_pred]
                price_forecast = [e.get("elec_price_amt_kwh", 0.0) / 1000.0 for _, e in sorted_pred]
                consumption_forecast = [e.get("load_mean_power_w", 0.0) for _, e in sorted_pred]

            total_cost = solution.get("total_costs_amt")
            total_revenue = solution.get("total_revenues_amt")
            total_losses = solution.get("total_losses_energy_wh")
            valid_from = solution.get("valid_from")

        # If no solution arrays but we have prediction series, try those
        if not pv_forecast:
            pv_forecast = await self._fetch_prediction_list("pvforecast_ac_power")
        if not price_forecast:
            raw_prices = await self._fetch_prediction_list("elecprice_marketprice_kwh")
            price_forecast = [p / 1000.0 for p in raw_prices] if raw_prices else []
        if not consumption_forecast:
            consumption_forecast = await self._fetch_prediction_list("loadakkudoktor_mean_power_w")

        total_balance = None
        if total_cost is not None and total_revenue is not None:
            total_balance = total_revenue - total_cost

        # Build data dict — use current EOS entity values for index 0 if arrays are empty
        # This ensures sensors show current state even before a full solution is available
        if not ac_charge_arr and current_ac_charge is not None:
            ac_charge_arr = [current_ac_charge]
        if not dc_charge_arr and current_dc_charge is not None:
            dc_charge_arr = [current_dc_charge]
        if not discharge_arr and current_discharge is not None:
            discharge_arr = [current_discharge]
        if not soc_arr and current_soc is not None:
            soc_arr = [round(current_soc * 100, 2)]
        if not cost_arr and current_cost is not None:
            cost_arr = [current_cost]
        if not revenue_arr and current_revenue is not None:
            revenue_arr = [current_revenue]
        if not grid_consumption_arr and current_grid_consumption is not None:
            grid_consumption_arr = [current_grid_consumption]
        if not grid_feedin_arr and current_grid_feedin is not None:
            grid_feedin_arr = [current_grid_feedin]
        if not load_arr and current_load is not None:
            load_arr = [current_load]
        if not losses_arr and current_losses is not None:
            losses_arr = [current_losses]

        return {
            "ac_charge": ac_charge_arr,
            "dc_charge": dc_charge_arr,
            "discharge_allowed": discharge_arr,
            "start_solution": valid_from,
            "battery_soc_forecast": soc_arr,
            "cost_per_hour": cost_arr,
            "revenue_per_hour": revenue_arr,
            "grid_consumption_per_hour": grid_consumption_arr,
            "grid_feedin_per_hour": grid_feedin_arr,
            "load_per_hour": load_arr,
            "losses_per_hour": losses_arr,
            "total_balance": total_balance,
            "total_cost": total_cost,
            "total_revenue": total_revenue,
            "total_losses": total_losses,
            "electricity_price": price_forecast,
            "pv_forecast": pv_forecast,
            "consumption_forecast": consumption_forecast,
            "price_forecast": price_forecast,
            "active_override": self.active_override,
            "energy_plan": {},
            "resource_status": {},
            "ev_charge_plan": {},
            "appliance_schedules": {},
            "raw_response": solution,
            "eos_entities_available": eos_entities_available,
            "last_update": dt_util.now().isoformat(),
            "last_success": True,
        }

    async def _fetch_prediction_list(self, key: str) -> list[float]:
        """Fetch a prediction series and return as ordered list of values."""
        try:
            result = await self._eos_client.get_prediction_series(key)
            data = result.get("data", {})
            if not data:
                return []
            sorted_items = sorted(data.items())
            return [float(v) for _, v in sorted_items]
        except Exception as err:
            _LOGGER.debug("Error fetching prediction series %s: %s", key, err)
            return []

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
            "eos_entities_available": False,
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
