"""Config flow for EOS HA integration."""
from __future__ import annotations

import asyncio
import logging
from typing import Any

import aiohttp
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_URL
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
    CONF_SOC_ENTITY,
    DEFAULT_BATTERY_CAPACITY,
    DEFAULT_INVERTER_POWER,
    DEFAULT_MAX_CHARGE_POWER,
    DEFAULT_MAX_SOC,
    DEFAULT_MIN_SOC,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)


class EOSHAOptionsFlow(config_entries.OptionsFlow):
    """Handle options flow for EOS HA (runtime config changes)."""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.FlowResult:
        """Handle options step - change entities and battery params."""
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        current = {**self.config_entry.data, **self.config_entry.options}

        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_PRICE_ENTITY,
                        default=current.get(CONF_PRICE_ENTITY),
                    ): selector.EntitySelector(
                        selector.EntitySelectorConfig(domain="sensor")
                    ),
                    vol.Required(
                        CONF_SOC_ENTITY,
                        default=current.get(CONF_SOC_ENTITY),
                    ): selector.EntitySelector(
                        selector.EntitySelectorConfig(
                            domain="sensor", device_class="battery"
                        )
                    ),
                    vol.Required(
                        CONF_CONSUMPTION_ENTITY,
                        default=current.get(CONF_CONSUMPTION_ENTITY),
                    ): selector.EntitySelector(
                        selector.EntitySelectorConfig(domain="sensor")
                    ),
                    vol.Required(
                        CONF_BATTERY_CAPACITY,
                        default=current.get(CONF_BATTERY_CAPACITY, DEFAULT_BATTERY_CAPACITY),
                    ): selector.NumberSelector(
                        selector.NumberSelectorConfig(
                            min=0.5, max=200.0, step=0.5,
                            unit_of_measurement="kWh",
                            mode=selector.NumberSelectorMode.BOX,
                        )
                    ),
                    vol.Required(
                        CONF_MAX_CHARGE_POWER,
                        default=current.get(CONF_MAX_CHARGE_POWER, DEFAULT_MAX_CHARGE_POWER),
                    ): selector.NumberSelector(
                        selector.NumberSelectorConfig(
                            min=100, max=50000, step=100,
                            unit_of_measurement="W",
                            mode=selector.NumberSelectorMode.BOX,
                        )
                    ),
                    vol.Required(
                        CONF_MIN_SOC,
                        default=current.get(CONF_MIN_SOC, DEFAULT_MIN_SOC),
                    ): selector.NumberSelector(
                        selector.NumberSelectorConfig(
                            min=0, max=100, step=1,
                            unit_of_measurement="%",
                            mode=selector.NumberSelectorMode.SLIDER,
                        )
                    ),
                    vol.Required(
                        CONF_MAX_SOC,
                        default=current.get(CONF_MAX_SOC, DEFAULT_MAX_SOC),
                    ): selector.NumberSelector(
                        selector.NumberSelectorConfig(
                            min=0, max=100, step=1,
                            unit_of_measurement="%",
                            mode=selector.NumberSelectorMode.SLIDER,
                        )
                    ),
                    vol.Required(
                        CONF_INVERTER_POWER,
                        default=current.get(CONF_INVERTER_POWER, DEFAULT_INVERTER_POWER),
                    ): selector.NumberSelector(
                        selector.NumberSelectorConfig(
                            min=100, max=100000, step=100,
                            unit_of_measurement="W",
                            mode=selector.NumberSelectorMode.BOX,
                        )
                    ),
                }
            ),
        )


class EOSHAConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for EOS HA."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialize the config flow."""
        self.data: dict[str, Any] = {}

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
            # Set unique ID to prevent duplicate entries
            await self.async_set_unique_id(DOMAIN)
            self._abort_if_unique_id_configured()

            # Get home location from HA config
            latitude = self.hass.config.latitude
            longitude = self.hass.config.longitude

            if latitude is None or longitude is None or latitude == 0 or longitude == 0:
                return self.async_abort(reason="no_home_location")

            # Validate EOS server
            eos_url = user_input[CONF_EOS_URL].rstrip("/")
            session = async_get_clientsession(self.hass)

            try:
                timeout = aiohttp.ClientTimeout(total=10)
                async with session.get(
                    f"{eos_url}/v1/health", timeout=timeout
                ) as response:
                    if response.status != 200:
                        errors["base"] = "invalid_response"
                    else:
                        data = await response.json()
                        if data.get("status") != "alive":
                            errors["base"] = "invalid_response"
                        else:
                            # Success - store data and proceed
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
                _LOGGER.exception("Unexpected error validating EOS server: %s", err)
                errors["base"] = "invalid_response"

        # Show form
        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_EOS_URL): str,
                }
            ),
            errors=errors,
        )

    async def async_step_entities(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.FlowResult:
        """Handle the second step - Entity Selection."""
        if user_input is not None:
            # Store entity selections
            self.data[CONF_PRICE_ENTITY] = user_input[CONF_PRICE_ENTITY]
            self.data[CONF_SOC_ENTITY] = user_input[CONF_SOC_ENTITY]
            self.data[CONF_CONSUMPTION_ENTITY] = user_input[CONF_CONSUMPTION_ENTITY]
            return await self.async_step_battery()

        # Show form with entity selectors
        return self.async_show_form(
            step_id="entities",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_PRICE_ENTITY): selector.EntitySelector(
                        selector.EntitySelectorConfig(domain="sensor")
                    ),
                    vol.Required(CONF_SOC_ENTITY): selector.EntitySelector(
                        selector.EntitySelectorConfig(
                            domain="sensor", device_class="battery"
                        )
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
        """Handle the third step - Battery Parameters."""
        if user_input is not None:
            # Store battery parameters
            self.data[CONF_BATTERY_CAPACITY] = user_input[CONF_BATTERY_CAPACITY]
            self.data[CONF_MAX_CHARGE_POWER] = user_input[CONF_MAX_CHARGE_POWER]
            self.data[CONF_MIN_SOC] = user_input[CONF_MIN_SOC]
            self.data[CONF_MAX_SOC] = user_input[CONF_MAX_SOC]
            self.data[CONF_INVERTER_POWER] = user_input[CONF_INVERTER_POWER]

            # Create config entry with all accumulated data
            return self.async_create_entry(title="EOS HA", data=self.data)

        # Show form with battery parameters
        return self.async_show_form(
            step_id="battery",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_BATTERY_CAPACITY, default=DEFAULT_BATTERY_CAPACITY
                    ): selector.NumberSelector(
                        selector.NumberSelectorConfig(
                            min=0.5,
                            max=200.0,
                            step=0.5,
                            unit_of_measurement="kWh",
                            mode=selector.NumberSelectorMode.BOX,
                        )
                    ),
                    vol.Required(
                        CONF_MAX_CHARGE_POWER, default=DEFAULT_MAX_CHARGE_POWER
                    ): selector.NumberSelector(
                        selector.NumberSelectorConfig(
                            min=100,
                            max=50000,
                            step=100,
                            unit_of_measurement="W",
                            mode=selector.NumberSelectorMode.BOX,
                        )
                    ),
                    vol.Required(CONF_MIN_SOC, default=DEFAULT_MIN_SOC): selector.NumberSelector(
                        selector.NumberSelectorConfig(
                            min=0,
                            max=100,
                            step=1,
                            unit_of_measurement="%",
                            mode=selector.NumberSelectorMode.SLIDER,
                        )
                    ),
                    vol.Required(CONF_MAX_SOC, default=DEFAULT_MAX_SOC): selector.NumberSelector(
                        selector.NumberSelectorConfig(
                            min=0,
                            max=100,
                            step=1,
                            unit_of_measurement="%",
                            mode=selector.NumberSelectorMode.SLIDER,
                        )
                    ),
                    vol.Required(
                        CONF_INVERTER_POWER, default=DEFAULT_INVERTER_POWER
                    ): selector.NumberSelector(
                        selector.NumberSelectorConfig(
                            min=100,
                            max=100000,
                            step=100,
                            unit_of_measurement="W",
                            mode=selector.NumberSelectorMode.BOX,
                        )
                    ),
                }
            ),
        )
