"""Config flow for EOS HA integration."""
from __future__ import annotations

import asyncio
import logging
from typing import Any

import aiohttp
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.helpers import selector
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import (
    CONF_SG_READY_ENABLED,
    CONF_SG_READY_SWITCH_1,
    CONF_SG_READY_SWITCH_2,
    CONF_APPLIANCES,
    CONF_BATTERY_ENERGY,
    CONF_BATTERY_GRID_POWER,
    CONF_BATTERY_PV_POWER,
    CONF_BATTERY_CAPACITY,
    CONF_BIDDING_ZONE,
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
    CONF_YEARLY_CONSUMPTION,
    DEFAULT_BATTERY_CAPACITY,
    DEFAULT_BIDDING_ZONE,
    DEFAULT_EV_CAPACITY,
    DEFAULT_EV_CHARGE_POWER,
    DEFAULT_EV_EFFICIENCY,
    DEFAULT_FEED_IN_TARIFF,
    DEFAULT_INVERTER_POWER,
    DEFAULT_MAX_CHARGE_POWER,
    DEFAULT_MAX_SOC,
    DEFAULT_MIN_SOC,
    DEFAULT_PV_AZIMUTH,
    DEFAULT_PV_INVERTER_POWER,
    DEFAULT_PV_POWER,
    DEFAULT_PV_TILT,
    DEFAULT_YEARLY_CONSUMPTION,
    DOMAIN,
    PRICE_SOURCE_AKKUDOKTOR,
    PRICE_SOURCE_ENERGYCHARTS,
    PRICE_SOURCE_EXTERNAL,
)

_LOGGER = logging.getLogger(__name__)

PRICE_SOURCE_OPTIONS = [
    selector.SelectOptionDict(value=PRICE_SOURCE_AKKUDOKTOR, label="EOS Akkudoktor (default)"),
    selector.SelectOptionDict(value=PRICE_SOURCE_ENERGYCHARTS, label="EOS EnergyCharts"),
    selector.SelectOptionDict(value=PRICE_SOURCE_EXTERNAL, label="External HA Sensor (Tibber etc.)"),
]


def _pv_array_schema(
    azimuth: int = DEFAULT_PV_AZIMUTH,
    tilt: int = DEFAULT_PV_TILT,
    power: int = DEFAULT_PV_POWER,
    inverter_power: int = DEFAULT_PV_INVERTER_POWER,
) -> vol.Schema:
    """Build schema for a single PV array."""
    return vol.Schema(
        {
            vol.Required("azimuth", default=azimuth): selector.NumberSelector(
                selector.NumberSelectorConfig(
                    min=0, max=360, step=1,
                    unit_of_measurement="°",
                    mode=selector.NumberSelectorMode.BOX,
                )
            ),
            vol.Required("tilt", default=tilt): selector.NumberSelector(
                selector.NumberSelectorConfig(
                    min=0, max=90, step=1,
                    unit_of_measurement="°",
                    mode=selector.NumberSelectorMode.BOX,
                )
            ),
            vol.Required("power", default=power): selector.NumberSelector(
                selector.NumberSelectorConfig(
                    min=1, max=100000, step=1,
                    unit_of_measurement="Wp",
                    mode=selector.NumberSelectorMode.BOX,
                )
            ),
            vol.Required("inverter_power", default=inverter_power): selector.NumberSelector(
                selector.NumberSelectorConfig(
                    min=1, max=100000, step=1,
                    unit_of_measurement="W",
                    mode=selector.NumberSelectorMode.BOX,
                )
            ),
            vol.Required("inverter_efficiency", default=0.9): selector.NumberSelector(
                selector.NumberSelectorConfig(
                    min=0.5, max=1.0, step=0.01,
                    mode=selector.NumberSelectorMode.BOX,
                )
            ),
        }
    )


# ---------------------------------------------------------------------------
# Options Flow
# ---------------------------------------------------------------------------

class EOSHAOptionsFlow(config_entries.OptionsFlow):
    """Handle options flow for EOS HA (runtime config changes)."""

    def __init__(self) -> None:
        self._pv_arrays: list[dict] = []
        self._pending: dict[str, Any] = {}
        self._initialized = False

    def _current(self) -> dict[str, Any]:
        """Get current effective config (data + options + pending changes)."""
        return {**self.config_entry.data, **self.config_entry.options, **self._pending}

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.FlowResult:
        """Main options menu."""
        if not self._initialized:
            current = {**self.config_entry.data, **self.config_entry.options}
            self._pv_arrays = list(current.get(CONF_PV_ARRAYS, []))
            self._initialized = True

        return self.async_show_menu(
            step_id="init",
            menu_options=["eos_server", "entities", "energy_meters", "battery", "battery_sensors", "pv_arrays", "price_source", "ev", "appliances", "feed_in_tariff", "sg_ready", "save_close"],
        )

    async def async_step_save_close(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.FlowResult:
        """Save all pending changes and close."""
        new_options = {**self.config_entry.options, **self._pending}
        return self.async_create_entry(title="", data=new_options)

    # -- EOS Server sub-step -----------------------------------------------

    async def async_step_eos_server(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.FlowResult:
        """Change EOS server URL."""
        errors: dict[str, str] = {}
        current = {**self.config_entry.data, **self.config_entry.options}

        if user_input is not None:
            eos_url = user_input[CONF_EOS_URL].rstrip("/")
            try:
                session = async_get_clientsession(self.hass)
                timeout = aiohttp.ClientTimeout(total=10)
                async with session.get(f"{eos_url}/v1/health", timeout=timeout) as response:
                    if response.status == 200:
                        # Update both data and options
                        self.hass.config_entries.async_update_entry(
                            self.config_entry,
                            data={**self.config_entry.data, CONF_EOS_URL: eos_url},
                        )
                        await self.hass.config_entries.async_reload(self.config_entry.entry_id)
                        return self.async_create_entry(title="", data={})
                    errors["base"] = "invalid_response"
            except aiohttp.ClientError:
                errors["base"] = "cannot_connect"
            except Exception:
                errors["base"] = "invalid_response"

        return self.async_show_form(
            step_id="eos_server",
            data_schema=vol.Schema({
                vol.Required(CONF_EOS_URL, default=current.get(CONF_EOS_URL, "")): str,
            }),
            errors=errors,
        )

    # -- Price source sub-step ----------------------------------------------

    async def async_step_price_source(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.FlowResult:
        """Change electricity price source."""
        if user_input is not None:
            self._pending[CONF_PRICE_SOURCE] = user_input[CONF_PRICE_SOURCE]

            if user_input[CONF_PRICE_SOURCE] == PRICE_SOURCE_ENERGYCHARTS:
                self._pending[CONF_BIDDING_ZONE] = user_input.get(CONF_BIDDING_ZONE, DEFAULT_BIDDING_ZONE)
            elif user_input[CONF_PRICE_SOURCE] == PRICE_SOURCE_EXTERNAL:
                self._pending[CONF_PRICE_ENTITY] = user_input.get(CONF_PRICE_ENTITY, "")

            return await self.async_step_init()

        current = self._current()
        current_source = current.get(CONF_PRICE_SOURCE, PRICE_SOURCE_AKKUDOKTOR)

        schema_dict: dict = {
            vol.Required(CONF_PRICE_SOURCE, default=current_source): selector.SelectSelector(
                selector.SelectSelectorConfig(
                    options=PRICE_SOURCE_OPTIONS,
                    mode=selector.SelectSelectorMode.DROPDOWN,
                )
            ),
            vol.Optional(CONF_BIDDING_ZONE, default=current.get(CONF_BIDDING_ZONE, DEFAULT_BIDDING_ZONE)): str,
            vol.Optional(CONF_PRICE_ENTITY, default=current.get(CONF_PRICE_ENTITY) or vol.UNDEFINED): selector.EntitySelector(
                selector.EntitySelectorConfig(domain="sensor")
            ),
        }

        return self.async_show_form(
            step_id="price_source",
            data_schema=vol.Schema(schema_dict),
        )

    # -- Entities sub-step --------------------------------------------------

    async def async_step_entities(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.FlowResult:
        """Change input entity mappings."""
        if user_input is not None:
            self._pending.update(user_input)
            return await self.async_step_init()

        current = self._current()
        current_source = current.get(CONF_PRICE_SOURCE, PRICE_SOURCE_EXTERNAL)

        schema_dict: dict = {}
        # Only show price entity if external source
        if current_source == PRICE_SOURCE_EXTERNAL:
            schema_dict[vol.Required(CONF_PRICE_ENTITY, default=current.get(CONF_PRICE_ENTITY))] = selector.EntitySelector(
                selector.EntitySelectorConfig(domain="sensor")
            )
        schema_dict[vol.Required(CONF_SOC_ENTITY, default=current.get(CONF_SOC_ENTITY))] = selector.EntitySelector(
            selector.EntitySelectorConfig(domain="sensor", device_class="battery")
        )

        return self.async_show_form(
            step_id="entities",
            data_schema=vol.Schema(schema_dict),
        )

    # -- Energy Meters sub-step ---------------------------------------------

    async def async_step_energy_meters(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.FlowResult:
        """Configure energy meter entities for EOS HA Adapter."""
        if user_input is not None:
            self._pending.update(user_input)
            return await self.async_step_init()

        current = self._current()
        return self.async_show_form(
            step_id="energy_meters",
            data_schema=vol.Schema(
                {
                    vol.Optional(CONF_LOAD_EMR_ENTITY, default=current.get(CONF_LOAD_EMR_ENTITY) or vol.UNDEFINED): selector.EntitySelector(
                        selector.EntitySelectorConfig(domain="sensor")
                    ),
                    vol.Optional(CONF_GRID_IMPORT_EMR_ENTITY, default=current.get(CONF_GRID_IMPORT_EMR_ENTITY) or vol.UNDEFINED): selector.EntitySelector(
                        selector.EntitySelectorConfig(domain="sensor")
                    ),
                    vol.Optional(CONF_GRID_EXPORT_EMR_ENTITY, default=current.get(CONF_GRID_EXPORT_EMR_ENTITY) or vol.UNDEFINED): selector.EntitySelector(
                        selector.EntitySelectorConfig(domain="sensor")
                    ),
                    vol.Optional(CONF_PV_PRODUCTION_EMR_ENTITY, default=current.get(CONF_PV_PRODUCTION_EMR_ENTITY) or vol.UNDEFINED): selector.EntitySelector(
                        selector.EntitySelectorConfig(domain="sensor")
                    ),
                    vol.Required(CONF_YEARLY_CONSUMPTION, default=current.get(CONF_YEARLY_CONSUMPTION, DEFAULT_YEARLY_CONSUMPTION)): selector.NumberSelector(
                        selector.NumberSelectorConfig(min=1000, max=100000, step=100, unit_of_measurement="kWh", mode=selector.NumberSelectorMode.BOX)
                    ),
                }
            ),
        )

    # -- Battery sub-step ---------------------------------------------------

    async def async_step_battery(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.FlowResult:
        """Change battery parameters."""
        if user_input is not None:
            self._pending.update(user_input)
            return await self.async_step_init()

        current = self._current()
        return self.async_show_form(
            step_id="battery",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_BATTERY_CAPACITY, default=current.get(CONF_BATTERY_CAPACITY, DEFAULT_BATTERY_CAPACITY)): selector.NumberSelector(
                        selector.NumberSelectorConfig(min=0.5, max=200.0, step=0.5, unit_of_measurement="kWh", mode=selector.NumberSelectorMode.BOX)
                    ),
                    vol.Required(CONF_MAX_CHARGE_POWER, default=current.get(CONF_MAX_CHARGE_POWER, DEFAULT_MAX_CHARGE_POWER)): selector.NumberSelector(
                        selector.NumberSelectorConfig(min=100, max=50000, step=100, unit_of_measurement="W", mode=selector.NumberSelectorMode.BOX)
                    ),
                    vol.Required(CONF_MIN_SOC, default=current.get(CONF_MIN_SOC, DEFAULT_MIN_SOC)): selector.NumberSelector(
                        selector.NumberSelectorConfig(min=0, max=100, step=1, unit_of_measurement="%", mode=selector.NumberSelectorMode.SLIDER)
                    ),
                    vol.Required(CONF_MAX_SOC, default=current.get(CONF_MAX_SOC, DEFAULT_MAX_SOC)): selector.NumberSelector(
                        selector.NumberSelectorConfig(min=0, max=100, step=1, unit_of_measurement="%", mode=selector.NumberSelectorMode.SLIDER)
                    ),
                    vol.Required(CONF_INVERTER_POWER, default=current.get(CONF_INVERTER_POWER, DEFAULT_INVERTER_POWER)): selector.NumberSelector(
                        selector.NumberSelectorConfig(min=100, max=100000, step=100, unit_of_measurement="W", mode=selector.NumberSelectorMode.BOX)
                    ),
                }
            ),
        )

    # -- PV Arrays sub-steps ------------------------------------------------

    async def async_step_pv_arrays(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.FlowResult:
        """Show PV arrays overview with add/remove/save."""
        if user_input is not None:
            action = user_input.get("action", "save")
            if action == "add":
                return await self.async_step_pv_add()
            if action.startswith("remove_"):
                idx = int(action.split("_", 1)[1])
                if 0 <= idx < len(self._pv_arrays):
                    self._pv_arrays.pop(idx)
                return await self.async_step_pv_arrays()
            # save & back to menu
            self._pending[CONF_PV_ARRAYS] = self._pv_arrays
            return await self.async_step_init()

        options = [
            selector.SelectOptionDict(value="add", label="➕ Add PV Array"),
        ]
        for i, arr in enumerate(self._pv_arrays):
            options.append(
                selector.SelectOptionDict(
                    value=f"remove_{i}",
                    label=f"❌ Remove #{i+1}: {arr['azimuth']}° / {arr['tilt']}° / {arr['power']}Wp",
                )
            )
        options.append(selector.SelectOptionDict(value="save", label="💾 Save & Close"))

        return self.async_show_form(
            step_id="pv_arrays",
            data_schema=vol.Schema(
                {
                    vol.Required("action", default="save"): selector.SelectSelector(
                        selector.SelectSelectorConfig(options=options, mode=selector.SelectSelectorMode.LIST)
                    ),
                }
            ),
        )

    async def async_step_pv_add(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.FlowResult:
        """Add a new PV array."""
        if user_input is not None:
            self._pv_arrays.append({
                "azimuth": int(user_input["azimuth"]),
                "tilt": int(user_input["tilt"]),
                "power": int(user_input["power"]),
                "inverter_power": int(user_input["inverter_power"]),
                "inverter_efficiency": float(user_input.get("inverter_efficiency", 0.9)),
            })
            return await self.async_step_pv_arrays()

        return self.async_show_form(
            step_id="pv_add",
            data_schema=_pv_array_schema(),
        )

    # -- EV sub-step --------------------------------------------------------

    async def async_step_ev(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.FlowResult:
        """Configure electric vehicle parameters."""
        if user_input is not None:
            self._pending.update(user_input)
            return await self.async_step_init()

        current = self._current()
        return self.async_show_form(
            step_id="ev",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_EV_ENABLED, default=current.get(CONF_EV_ENABLED, False)): bool,
                    vol.Required(CONF_EV_CAPACITY, default=current.get(CONF_EV_CAPACITY, DEFAULT_EV_CAPACITY)): selector.NumberSelector(
                        selector.NumberSelectorConfig(min=1.0, max=200.0, step=0.5, unit_of_measurement="kWh", mode=selector.NumberSelectorMode.BOX)
                    ),
                    vol.Required(CONF_EV_CHARGE_POWER, default=current.get(CONF_EV_CHARGE_POWER, DEFAULT_EV_CHARGE_POWER)): selector.NumberSelector(
                        selector.NumberSelectorConfig(min=1000, max=50000, step=100, unit_of_measurement="W", mode=selector.NumberSelectorMode.BOX)
                    ),
                    vol.Required(CONF_EV_EFFICIENCY, default=current.get(CONF_EV_EFFICIENCY, DEFAULT_EV_EFFICIENCY)): selector.NumberSelector(
                        selector.NumberSelectorConfig(min=0.5, max=1.0, step=0.01, mode=selector.NumberSelectorMode.BOX)
                    ),
                    vol.Optional(CONF_EV_SOC_ENTITY, default=current.get(CONF_EV_SOC_ENTITY) or vol.UNDEFINED): selector.EntitySelector(
                        selector.EntitySelectorConfig(domain="sensor")
                    ),
                }
            ),
        )

    # -- Appliances sub-step ------------------------------------------------

    async def async_step_appliances(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.FlowResult:
        """Manage home appliances (flexible loads)."""
        current = self._current()
        if not hasattr(self, "_appliances"):
            self._appliances = list(current.get(CONF_APPLIANCES, []))

        if user_input is not None:
            action = user_input.get("action", "save")
            if action == "add":
                self._edit_appliance_idx = None
                return await self.async_step_appliance_edit()
            if action.startswith("edit_"):
                idx = int(action.split("_", 1)[1])
                if 0 <= idx < len(self._appliances):
                    self._edit_appliance_idx = idx
                    return await self.async_step_appliance_edit()
            if action.startswith("remove_"):
                idx = int(action.split("_", 1)[1])
                if 0 <= idx < len(self._appliances):
                    self._appliances.pop(idx)
                return await self.async_step_appliances()
            # save & back to menu
            self._pending[CONF_APPLIANCES] = self._appliances
            return await self.async_step_init()

        options = [
            selector.SelectOptionDict(value="add", label="➕ Add Appliance"),
        ]
        for i, app in enumerate(self._appliances):
            duration = app.get("duration_h", 0)
            if isinstance(duration, (int, float)) and duration != int(duration):
                dur_h = int(duration)
                dur_m = int((duration - dur_h) * 60)
                dur_str = f"{dur_h}h{dur_m:02d}m"
            else:
                dur_str = f"{int(duration)}h"
            window = ""
            if app.get("window_start") or app.get("window_end"):
                ws = app.get("window_start", "—")
                we = app.get("window_end", "—")
                window = f", {ws}-{we}"
            options.append(
                selector.SelectOptionDict(
                    value=f"edit_{i}",
                    label=f"✏️ {app['name']} ({app['consumption_wh']}Wh, {dur_str}{window})",
                )
            )
            options.append(
                selector.SelectOptionDict(
                    value=f"remove_{i}",
                    label=f"    ❌ Remove {app['name']}",
                )
            )
        options.append(selector.SelectOptionDict(value="save", label="💾 Save & Back"))

        return self.async_show_form(
            step_id="appliances",
            data_schema=vol.Schema(
                {
                    vol.Required("action", default="save"): selector.SelectSelector(
                        selector.SelectSelectorConfig(options=options, mode=selector.SelectSelectorMode.LIST)
                    ),
                }
            ),
        )

    async def async_step_appliance_edit(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.FlowResult:
        """Add or edit a home appliance."""
        idx = getattr(self, "_edit_appliance_idx", None)
        existing = self._appliances[idx] if idx is not None else None

        if user_input is not None:
            # Parse duration from HH:MM dict or number
            duration_raw = user_input.get("duration", {})
            if isinstance(duration_raw, dict):
                dur_hours = duration_raw.get("hours", 0) or 0
                dur_minutes = duration_raw.get("minutes", 0) or 0
                duration_h = dur_hours + dur_minutes / 60.0
            else:
                duration_h = float(duration_raw) if duration_raw else 1.0
            # Round to nearest 0.5h for EOS compatibility
            duration_h = round(duration_h * 2) / 2
            if duration_h < 0.5:
                duration_h = 0.5

            app = {
                "name": user_input["name"],
                "device_id": user_input["name"].lower().replace(" ", "_"),
                "consumption_wh": int(user_input["consumption_wh"]),
                "duration_h": duration_h if duration_h != int(duration_h) else int(duration_h),
            }
            # Time window (optional — both are independent)
            ws = user_input.get("window_start")
            we = user_input.get("window_end")
            if ws:
                app["window_start"] = ws
            if we:
                app["window_end"] = we

            if idx is not None:
                self._appliances[idx] = app
            else:
                self._appliances.append(app)
            return await self.async_step_appliances()

        # Defaults from existing appliance or fresh
        def_name = existing["name"] if existing else "Hot Water"
        def_wh = existing["consumption_wh"] if existing else 2000
        def_dur_h = existing.get("duration_h", 2) if existing else 2
        # Convert duration_h to hours/minutes for selector
        if isinstance(def_dur_h, (int, float)):
            dur_h_int = int(def_dur_h)
            dur_m_int = int((def_dur_h - dur_h_int) * 60)
        else:
            dur_h_int = 2
            dur_m_int = 0
        def_ws = existing.get("window_start") if existing else None
        def_we = existing.get("window_end") if existing else None

        schema_dict: dict = {
            vol.Required("name", default=def_name): str,
            vol.Required("consumption_wh", default=def_wh): selector.NumberSelector(
                selector.NumberSelectorConfig(min=100, max=50000, step=100, unit_of_measurement="Wh", mode=selector.NumberSelectorMode.BOX)
            ),
            vol.Required("duration", default={"hours": dur_h_int, "minutes": dur_m_int}): selector.DurationSelector(
                selector.DurationSelectorConfig(enable_day=False)
            ),
        }
        # Time windows are fully optional
        if def_ws:
            schema_dict[vol.Optional("window_start", default=def_ws)] = selector.TimeSelector()
        else:
            schema_dict[vol.Optional("window_start")] = selector.TimeSelector()
        if def_we:
            schema_dict[vol.Optional("window_end", default=def_we)] = selector.TimeSelector()
        else:
            schema_dict[vol.Optional("window_end")] = selector.TimeSelector()

        return self.async_show_form(
            step_id="appliance_edit",
            data_schema=vol.Schema(schema_dict),
        )

    # -- SG-Ready sub-step --------------------------------------------------

    async def async_step_sg_ready(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.FlowResult:
        """Configure SG-Ready heat pump control."""
        if user_input is not None:
            self._pending.update(user_input)
            return await self.async_step_init()

        current = self._current()
        return self.async_show_form(
            step_id="sg_ready",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_SG_READY_ENABLED, default=current.get(CONF_SG_READY_ENABLED, False)): bool,
                    vol.Optional(CONF_SG_READY_SWITCH_1, default=current.get(CONF_SG_READY_SWITCH_1) or vol.UNDEFINED): selector.EntitySelector(
                        selector.EntitySelectorConfig(domain="switch")
                    ),
                    vol.Optional(CONF_SG_READY_SWITCH_2, default=current.get(CONF_SG_READY_SWITCH_2) or vol.UNDEFINED): selector.EntitySelector(
                        selector.EntitySelectorConfig(domain="switch")
                    ),
                }
            ),
        )

    # -- Battery Sensors sub-step -------------------------------------------

    async def async_step_battery_sensors(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.FlowResult:
        """Configure battery sensor entities for storage price tracking."""
        if user_input is not None:
            self._pending.update(user_input)
            return await self.async_step_init()

        current = self._current()
        return self.async_show_form(
            step_id="battery_sensors",
            data_schema=vol.Schema(
                {
                    vol.Optional(CONF_BATTERY_GRID_POWER, default=current.get(CONF_BATTERY_GRID_POWER) or vol.UNDEFINED): selector.EntitySelector(
                        selector.EntitySelectorConfig(domain="sensor")
                    ),
                    vol.Optional(CONF_BATTERY_PV_POWER, default=current.get(CONF_BATTERY_PV_POWER) or vol.UNDEFINED): selector.EntitySelector(
                        selector.EntitySelectorConfig(domain="sensor")
                    ),
                    vol.Optional(CONF_BATTERY_ENERGY, default=current.get(CONF_BATTERY_ENERGY) or vol.UNDEFINED): selector.EntitySelector(
                        selector.EntitySelectorConfig(domain="sensor")
                    ),
                }
            ),
        )

    # -- Feed-in Tariff sub-step --------------------------------------------

    async def async_step_feed_in_tariff(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.FlowResult:
        """Configure feed-in tariff."""
        if user_input is not None:
            self._pending.update(user_input)
            return await self.async_step_init()

        current = self._current()
        return self.async_show_form(
            step_id="feed_in_tariff",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_FEED_IN_TARIFF, default=current.get(CONF_FEED_IN_TARIFF, DEFAULT_FEED_IN_TARIFF)): selector.NumberSelector(
                        selector.NumberSelectorConfig(min=0.0, max=0.5, step=0.001, unit_of_measurement="EUR/kWh", mode=selector.NumberSelectorMode.BOX)
                    ),
                }
            ),
        )


# ---------------------------------------------------------------------------
# Config Flow (initial setup)
# ---------------------------------------------------------------------------

class EOSHAConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for EOS HA."""

    VERSION = 1

    def __init__(self) -> None:
        self.data: dict[str, Any] = {}
        self._pv_arrays: list[dict] = []

    @staticmethod
    def async_get_options_flow(config_entry):
        return EOSHAOptionsFlow()

    async def _detect_eos_addon(self) -> str | None:
        """Try to detect a running EOS addon via Supervisor API."""
        try:
            import os
            supervisor_token = os.environ.get("SUPERVISOR_TOKEN")
            if not supervisor_token:
                _LOGGER.debug("No SUPERVISOR_TOKEN, skipping addon detection")
                return None

            session = async_get_clientsession(self.hass)
            headers = {"Authorization": f"Bearer {supervisor_token}"}
            async with session.get(
                "http://supervisor/addons", headers=headers, timeout=aiohttp.ClientTimeout(total=5)
            ) as resp:
                if resp.status != 200:
                    _LOGGER.debug("Supervisor API returned %s", resp.status)
                    return None
                data = await resp.json()

            for addon in data.get("data", {}).get("addons", []):
                slug = addon.get("slug", "")
                name = addon.get("name", "")
                state = addon.get("state", "")
                _LOGGER.debug("Checking addon: slug=%s, name=%s, state=%s", slug, name, state)
                # Match EOS addon by slug or name containing "eos"
                if "eos" in slug.lower() and state == "started":
                    # Addon hostname: slug with _ replaced by -
                    hostname = slug.replace("_", "-")
                    # Try common EOS ports
                    for port in (8503, 8504):
                        url = f"http://{hostname}:{port}"
                        try:
                            async with session.get(
                                f"{url}/v1/health", timeout=aiohttp.ClientTimeout(total=5)
                            ) as health_resp:
                                if health_resp.status == 200:
                                    health = await health_resp.json()
                                    if health.get("status") == "alive":
                                        _LOGGER.info("Auto-detected EOS addon at %s (slug=%s)", url, slug)
                                        return url
                        except Exception:
                            _LOGGER.debug("Health check failed for %s", url)
                    # If health check failed, still suggest the default URL
                    fallback = f"http://{hostname}:8503"
                    _LOGGER.warning("EOS addon found (slug=%s) but health check failed, suggesting %s", slug, fallback)
                    return fallback
        except Exception as err:
            _LOGGER.debug("Addon detection failed: %s", err)
        return None

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.FlowResult:
        """Handle the initial step - EOS Server URL."""
        errors: dict[str, str] = {}

        if user_input is None:
            # Try auto-detection before showing the form
            detected_url = await self._detect_eos_addon()
            if detected_url:
                self._detected_url = detected_url

        if user_input is not None:
            # Unique ID based on EOS server URL to allow multiple instances
            eos_url = user_input[CONF_EOS_URL].rstrip("/")
            await self.async_set_unique_id(f"{DOMAIN}_{eos_url}")
            self._abort_if_unique_id_configured()

            latitude = self.hass.config.latitude
            longitude = self.hass.config.longitude
            if not latitude or not longitude:
                return self.async_abort(reason="no_home_location")

            eos_url = user_input[CONF_EOS_URL].rstrip("/")
            session = async_get_clientsession(self.hass)

            try:
                timeout = aiohttp.ClientTimeout(total=10)
                async with session.get(f"{eos_url}/v1/health", timeout=timeout) as response:
                    if response.status != 200:
                        errors["base"] = "invalid_response"
                    else:
                        data = await response.json()
                        if data.get("status") != "alive":
                            errors["base"] = "invalid_response"
                        else:
                            self.data[CONF_EOS_URL] = eos_url
                            self.data["latitude"] = latitude
                            self.data["longitude"] = longitude
                            self.data["eos_version"] = data.get("version", "unknown")
                            return await self.async_step_price_source()
            except asyncio.TimeoutError:
                errors["base"] = "timeout"
            except aiohttp.ClientError:
                errors["base"] = "cannot_connect"
            except Exception as err:
                _LOGGER.exception("Unexpected error: %s", err)
                errors["base"] = "invalid_response"

        detected_url = getattr(self, "_detected_url", None)
        default_url = detected_url or ""
        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema({
                vol.Required(CONF_EOS_URL, default=default_url): str,
            }),
            errors=errors,
            description_placeholders={
                "detected": f"EOS Addon erkannt: {default_url}" if detected_url else "",
            },
        )

    async def async_step_price_source(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.FlowResult:
        """Handle price source selection."""
        if user_input is not None:
            self.data[CONF_PRICE_SOURCE] = user_input[CONF_PRICE_SOURCE]
            if user_input[CONF_PRICE_SOURCE] == PRICE_SOURCE_ENERGYCHARTS:
                self.data[CONF_BIDDING_ZONE] = user_input.get(CONF_BIDDING_ZONE, DEFAULT_BIDDING_ZONE)
            if user_input[CONF_PRICE_SOURCE] == PRICE_SOURCE_EXTERNAL:
                return await self.async_step_entities()
            else:
                # Skip price entity, go to SOC/consumption entities
                return await self.async_step_entities_no_price()

        schema_dict: dict = {
            vol.Required(CONF_PRICE_SOURCE, default=PRICE_SOURCE_AKKUDOKTOR): selector.SelectSelector(
                selector.SelectSelectorConfig(
                    options=PRICE_SOURCE_OPTIONS,
                    mode=selector.SelectSelectorMode.DROPDOWN,
                )
            ),
            vol.Optional(CONF_BIDDING_ZONE, default=DEFAULT_BIDDING_ZONE): str,
        }

        return self.async_show_form(
            step_id="price_source",
            data_schema=vol.Schema(schema_dict),
        )

    async def async_step_entities(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.FlowResult:
        """Handle entity selection (with price entity for external source)."""
        if user_input is not None:
            self.data[CONF_PRICE_ENTITY] = user_input[CONF_PRICE_ENTITY]
            self.data[CONF_SOC_ENTITY] = user_input[CONF_SOC_ENTITY]
            return await self.async_step_battery()

        return self.async_show_form(
            step_id="entities",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_PRICE_ENTITY): selector.EntitySelector(
                        selector.EntitySelectorConfig(domain="sensor")
                    ),
                    vol.Required(CONF_SOC_ENTITY): selector.EntitySelector(
                        selector.EntitySelectorConfig(domain="sensor", device_class="battery")
                    ),
                }
            ),
        )

    async def async_step_entities_no_price(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.FlowResult:
        """Handle entity selection (without price entity — EOS provides prices)."""
        if user_input is not None:
            self.data[CONF_SOC_ENTITY] = user_input[CONF_SOC_ENTITY]
            return await self.async_step_battery()

        return self.async_show_form(
            step_id="entities_no_price",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_SOC_ENTITY): selector.EntitySelector(
                        selector.EntitySelectorConfig(domain="sensor", device_class="battery")
                    ),
                }
            ),
        )

    async def async_step_battery(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.FlowResult:
        """Handle battery parameters."""
        if user_input is not None:
            self.data[CONF_BATTERY_CAPACITY] = user_input[CONF_BATTERY_CAPACITY]
            self.data[CONF_MAX_CHARGE_POWER] = user_input[CONF_MAX_CHARGE_POWER]
            self.data[CONF_MIN_SOC] = user_input[CONF_MIN_SOC]
            self.data[CONF_MAX_SOC] = user_input[CONF_MAX_SOC]
            self.data[CONF_INVERTER_POWER] = user_input[CONF_INVERTER_POWER]
            self.data[CONF_FEED_IN_TARIFF] = user_input.get(CONF_FEED_IN_TARIFF, DEFAULT_FEED_IN_TARIFF)
            return await self.async_step_battery_sensors()

        return self.async_show_form(
            step_id="battery",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_BATTERY_CAPACITY, default=DEFAULT_BATTERY_CAPACITY): selector.NumberSelector(
                        selector.NumberSelectorConfig(min=0.5, max=200.0, step=0.5, unit_of_measurement="kWh", mode=selector.NumberSelectorMode.BOX)
                    ),
                    vol.Required(CONF_MAX_CHARGE_POWER, default=DEFAULT_MAX_CHARGE_POWER): selector.NumberSelector(
                        selector.NumberSelectorConfig(min=100, max=50000, step=100, unit_of_measurement="W", mode=selector.NumberSelectorMode.BOX)
                    ),
                    vol.Required(CONF_MIN_SOC, default=DEFAULT_MIN_SOC): selector.NumberSelector(
                        selector.NumberSelectorConfig(min=0, max=100, step=1, unit_of_measurement="%", mode=selector.NumberSelectorMode.SLIDER)
                    ),
                    vol.Required(CONF_MAX_SOC, default=DEFAULT_MAX_SOC): selector.NumberSelector(
                        selector.NumberSelectorConfig(min=0, max=100, step=1, unit_of_measurement="%", mode=selector.NumberSelectorMode.SLIDER)
                    ),
                    vol.Required(CONF_INVERTER_POWER, default=DEFAULT_INVERTER_POWER): selector.NumberSelector(
                        selector.NumberSelectorConfig(min=100, max=100000, step=100, unit_of_measurement="W", mode=selector.NumberSelectorMode.BOX)
                    ),
                    vol.Required(CONF_FEED_IN_TARIFF, default=DEFAULT_FEED_IN_TARIFF): selector.NumberSelector(
                        selector.NumberSelectorConfig(min=0.0, max=0.5, step=0.001, unit_of_measurement="EUR/kWh", mode=selector.NumberSelectorMode.BOX)
                    ),
                }
            ),
        )

    async def async_step_battery_sensors(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.FlowResult:
        """Configure battery sensor entities for storage price tracking (optional)."""
        if user_input is not None:
            self.data.update(user_input)
            return await self.async_step_energy_meters()

        return self.async_show_form(
            step_id="battery_sensors",
            data_schema=vol.Schema(
                {
                    vol.Optional(CONF_BATTERY_GRID_POWER): selector.EntitySelector(
                        selector.EntitySelectorConfig(domain="sensor")
                    ),
                    vol.Optional(CONF_BATTERY_PV_POWER): selector.EntitySelector(
                        selector.EntitySelectorConfig(domain="sensor")
                    ),
                    vol.Optional(CONF_BATTERY_ENERGY): selector.EntitySelector(
                        selector.EntitySelectorConfig(domain="sensor")
                    ),
                }
            ),
        )

    async def async_step_energy_meters(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.FlowResult:
        """Configure energy meter entities for EOS HA Adapter (optional)."""
        if user_input is not None:
            self.data.update(user_input)
            return await self.async_step_ev()

        return self.async_show_form(
            step_id="energy_meters",
            data_schema=vol.Schema(
                {
                    vol.Optional(CONF_LOAD_EMR_ENTITY): selector.EntitySelector(
                        selector.EntitySelectorConfig(domain="sensor")
                    ),
                    vol.Optional(CONF_GRID_IMPORT_EMR_ENTITY): selector.EntitySelector(
                        selector.EntitySelectorConfig(domain="sensor")
                    ),
                    vol.Optional(CONF_GRID_EXPORT_EMR_ENTITY): selector.EntitySelector(
                        selector.EntitySelectorConfig(domain="sensor")
                    ),
                    vol.Optional(CONF_PV_PRODUCTION_EMR_ENTITY): selector.EntitySelector(
                        selector.EntitySelectorConfig(domain="sensor")
                    ),
                    vol.Required(CONF_YEARLY_CONSUMPTION, default=DEFAULT_YEARLY_CONSUMPTION): selector.NumberSelector(
                        selector.NumberSelectorConfig(min=1000, max=100000, step=100, unit_of_measurement="kWh", mode=selector.NumberSelectorMode.BOX)
                    ),
                }
            ),
        )

    async def async_step_ev(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.FlowResult:
        """Configure electric vehicle (optional)."""
        if user_input is not None:
            self.data.update(user_input)
            return await self.async_step_pv_overview()

        return self.async_show_form(
            step_id="ev",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_EV_ENABLED, default=False): bool,
                    vol.Required(CONF_EV_CAPACITY, default=DEFAULT_EV_CAPACITY): selector.NumberSelector(
                        selector.NumberSelectorConfig(min=1.0, max=200.0, step=0.5, unit_of_measurement="kWh", mode=selector.NumberSelectorMode.BOX)
                    ),
                    vol.Required(CONF_EV_CHARGE_POWER, default=DEFAULT_EV_CHARGE_POWER): selector.NumberSelector(
                        selector.NumberSelectorConfig(min=1000, max=50000, step=100, unit_of_measurement="W", mode=selector.NumberSelectorMode.BOX)
                    ),
                    vol.Required(CONF_EV_EFFICIENCY, default=DEFAULT_EV_EFFICIENCY): selector.NumberSelector(
                        selector.NumberSelectorConfig(min=0.5, max=1.0, step=0.01, mode=selector.NumberSelectorMode.BOX)
                    ),
                    vol.Optional(CONF_EV_SOC_ENTITY): selector.EntitySelector(
                        selector.EntitySelectorConfig(domain="sensor")
                    ),
                }
            ),
        )

    async def async_step_pv_overview(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.FlowResult:
        """PV arrays overview during setup."""
        if user_input is not None:
            action = user_input.get("action", "finish")
            if action == "add":
                return await self.async_step_pv_add()
            if str(action).startswith("remove_"):
                idx = int(action.split("_", 1)[1])
                if 0 <= idx < len(self._pv_arrays):
                    self._pv_arrays.pop(idx)
                return await self.async_step_pv_overview()
            # finish
            self.data[CONF_PV_ARRAYS] = self._pv_arrays
            return self.async_create_entry(title="EOS HA", data=self.data)

        options = [
            selector.SelectOptionDict(value="add", label="➕ Add PV Array"),
        ]
        for i, arr in enumerate(self._pv_arrays):
            options.append(
                selector.SelectOptionDict(
                    value=f"remove_{i}",
                    label=f"❌ Remove #{i+1}: {arr['azimuth']}° / {arr['tilt']}° / {arr['power']}Wp",
                )
            )
        options.append(selector.SelectOptionDict(value="finish", label="✅ Finish Setup"))

        return self.async_show_form(
            step_id="pv_overview",
            data_schema=vol.Schema(
                {
                    vol.Required("action", default="finish"): selector.SelectSelector(
                        selector.SelectSelectorConfig(options=options, mode=selector.SelectSelectorMode.LIST)
                    ),
                }
            ),
        )

    async def async_step_pv_add(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.FlowResult:
        """Add a PV array during setup."""
        if user_input is not None:
            self._pv_arrays.append({
                "azimuth": int(user_input["azimuth"]),
                "tilt": int(user_input["tilt"]),
                "power": int(user_input["power"]),
                "inverter_power": int(user_input["inverter_power"]),
                "inverter_efficiency": float(user_input.get("inverter_efficiency", 0.9)),
            })
            return await self.async_step_pv_overview()

        return self.async_show_form(
            step_id="pv_add",
            data_schema=_pv_array_schema(),
        )
