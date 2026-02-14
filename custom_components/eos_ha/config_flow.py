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
    CONF_BATTERY_CAPACITY,
    CONF_CONSUMPTION_ENTITY,
    CONF_EOS_URL,
    CONF_INVERTER_POWER,
    CONF_MAX_CHARGE_POWER,
    CONF_MAX_SOC,
    CONF_MIN_SOC,
    CONF_PRICE_ENTITY,
    CONF_PV_ARRAYS,
    CONF_SOC_ENTITY,
    DEFAULT_BATTERY_CAPACITY,
    DEFAULT_INVERTER_POWER,
    DEFAULT_MAX_CHARGE_POWER,
    DEFAULT_MAX_SOC,
    DEFAULT_MIN_SOC,
    DEFAULT_PV_AZIMUTH,
    DEFAULT_PV_INVERTER_POWER,
    DEFAULT_PV_POWER,
    DEFAULT_PV_TILT,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)


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
                    min=100, max=100000, step=100,
                    unit_of_measurement="Wp",
                    mode=selector.NumberSelectorMode.BOX,
                )
            ),
            vol.Required("inverter_power", default=inverter_power): selector.NumberSelector(
                selector.NumberSelectorConfig(
                    min=100, max=100000, step=100,
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
        """Initialize options flow."""
        self._pv_arrays: list[dict] = []

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.FlowResult:
        """Main options menu."""
        current = {**self.config_entry.data, **self.config_entry.options}
        self._pv_arrays = list(current.get(CONF_PV_ARRAYS, []))

        return self.async_show_menu(
            step_id="init",
            menu_options=["entities", "battery", "pv_arrays"],
        )

    # -- Entities sub-step --------------------------------------------------

    async def async_step_entities(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.FlowResult:
        """Change input entity mappings."""
        if user_input is not None:
            new_options = {**self.config_entry.options, **user_input}
            return self.async_create_entry(title="", data=new_options)

        current = {**self.config_entry.data, **self.config_entry.options}
        return self.async_show_form(
            step_id="entities",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_PRICE_ENTITY, default=current.get(CONF_PRICE_ENTITY)): selector.EntitySelector(
                        selector.EntitySelectorConfig(domain="sensor")
                    ),
                    vol.Required(CONF_SOC_ENTITY, default=current.get(CONF_SOC_ENTITY)): selector.EntitySelector(
                        selector.EntitySelectorConfig(domain="sensor", device_class="battery")
                    ),
                    vol.Required(CONF_CONSUMPTION_ENTITY, default=current.get(CONF_CONSUMPTION_ENTITY)): selector.EntitySelector(
                        selector.EntitySelectorConfig(domain="sensor")
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
            new_options = {**self.config_entry.options, **user_input}
            return self.async_create_entry(title="", data=new_options)

        current = {**self.config_entry.data, **self.config_entry.options}
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
            # save
            new_options = {**self.config_entry.options, CONF_PV_ARRAYS: self._pv_arrays}
            return self.async_create_entry(title="", data=new_options)

        # Build menu options
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

        desc = "No PV arrays configured." if not self._pv_arrays else ""
        for i, arr in enumerate(self._pv_arrays):
            desc += f"\n**Array #{i+1}:** Azimuth {arr['azimuth']}°, Tilt {arr['tilt']}°, {arr['power']}Wp, Inverter {arr['inverter_power']}W"

        return self.async_show_form(
            step_id="pv_arrays",
            data_schema=vol.Schema(
                {
                    vol.Required("action", default="save"): selector.SelectSelector(
                        selector.SelectSelectorConfig(options=options, mode=selector.SelectSelectorMode.LIST)
                    ),
                }
            ),
            description_placeholders={"arrays_info": desc.strip()},
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


# ---------------------------------------------------------------------------
# Config Flow (initial setup)
# ---------------------------------------------------------------------------

class EOSHAConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for EOS HA."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialize the config flow."""
        self.data: dict[str, Any] = {}
        self._pv_arrays: list[dict] = []

    @staticmethod
    def async_get_options_flow(config_entry):
        """Get the options flow handler."""
        return EOSHAOptionsFlow()

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.FlowResult:
        """Handle the initial step - EOS Server URL."""
        errors: dict[str, str] = {}

        if user_input is not None:
            await self.async_set_unique_id(DOMAIN)
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
                            return await self.async_step_entities()
            except asyncio.TimeoutError:
                errors["base"] = "timeout"
            except aiohttp.ClientError:
                errors["base"] = "cannot_connect"
            except Exception as err:
                _LOGGER.exception("Unexpected error: %s", err)
                errors["base"] = "invalid_response"

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema({vol.Required(CONF_EOS_URL): str}),
            errors=errors,
        )

    async def async_step_entities(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.FlowResult:
        """Handle entity selection."""
        if user_input is not None:
            self.data[CONF_PRICE_ENTITY] = user_input[CONF_PRICE_ENTITY]
            self.data[CONF_SOC_ENTITY] = user_input[CONF_SOC_ENTITY]
            self.data[CONF_CONSUMPTION_ENTITY] = user_input[CONF_CONSUMPTION_ENTITY]
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
                    vol.Required(CONF_CONSUMPTION_ENTITY): selector.EntitySelector(
                        selector.EntitySelectorConfig(domain="sensor")
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
            return await self.async_step_pv_overview()

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
                }
            ),
        )

    async def async_step_pv_overview(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.FlowResult:
        """PV arrays overview during setup — add arrays or finish."""
        if user_input is not None:
            action = user_input.get("action", "finish")
            if action == "add":
                return await self.async_step_pv_add()
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

        if user_input and str(user_input.get("action", "")).startswith("remove_"):
            idx = int(user_input["action"].split("_", 1)[1])
            if 0 <= idx < len(self._pv_arrays):
                self._pv_arrays.pop(idx)
            return await self.async_step_pv_overview()

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
