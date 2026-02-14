"""Button platform for EOS HA integration."""
from __future__ import annotations

import logging

from homeassistant.components.button import ButtonEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import CONF_BATTERY_ENERGY, DOMAIN
from .coordinator import EOSCoordinator

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up EOS HA buttons from a config entry."""
    coordinator: EOSCoordinator = config_entry.runtime_data
    current = {**config_entry.data, **config_entry.options}

    entities: list[ButtonEntity] = [
        EOSOptimizeNowButton(coordinator),
        EOSUpdatePredictionsButton(coordinator),
    ]
    if current.get(CONF_BATTERY_ENERGY):
        entities.append(EOSBatteryPriceResetButton(coordinator))

    async_add_entities(entities)


class EOSOptimizeNowButton(ButtonEntity):
    """Button to trigger immediate optimization."""

    _attr_has_entity_name = True
    _attr_name = "Optimize Now"
    _attr_icon = "mdi:flash"

    def __init__(self, coordinator: EOSCoordinator) -> None:
        self._coordinator = coordinator
        self._attr_unique_id = (
            f"{coordinator.config_entry.entry_id}_optimize_now"
        )
        self._attr_device_info = {
            "identifiers": {(DOMAIN, coordinator.config_entry.entry_id)},
            "name": "EOS",
            "manufacturer": "Akkudoktor",
        }

    async def async_press(self) -> None:
        """Trigger optimization."""
        await self.hass.services.async_call(
            DOMAIN, "optimize_now", {}, blocking=True
        )


class EOSUpdatePredictionsButton(ButtonEntity):
    """Button to trigger prediction update."""

    _attr_has_entity_name = True
    _attr_name = "Update Predictions"
    _attr_icon = "mdi:refresh"

    def __init__(self, coordinator: EOSCoordinator) -> None:
        self._coordinator = coordinator
        self._attr_unique_id = (
            f"{coordinator.config_entry.entry_id}_update_predictions"
        )
        self._attr_device_info = {
            "identifiers": {(DOMAIN, coordinator.config_entry.entry_id)},
            "name": "EOS",
            "manufacturer": "Akkudoktor",
        }

    async def async_press(self) -> None:
        """Trigger prediction update."""
        await self.hass.services.async_call(
            DOMAIN, "update_predictions", {}, blocking=True
        )


class EOSBatteryPriceResetButton(ButtonEntity):
    """Button to reset the battery storage price sensor to zero."""

    _attr_has_entity_name = True
    _attr_name = "Reset Battery Price"
    _attr_icon = "mdi:battery-sync"

    def __init__(self, coordinator: EOSCoordinator) -> None:
        self._coordinator = coordinator
        self._attr_unique_id = (
            f"{coordinator.config_entry.entry_id}_reset_battery_price"
        )
        self._attr_device_info = {
            "identifiers": {(DOMAIN, coordinator.config_entry.entry_id)},
            "name": "EOS",
            "manufacturer": "Akkudoktor",
        }

    async def async_press(self) -> None:
        """Handle button press — reset battery storage price via service."""
        await self.hass.services.async_call(
            DOMAIN, "reset_battery_price", {}, blocking=True
        )
