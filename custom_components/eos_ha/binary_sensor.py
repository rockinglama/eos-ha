"""Binary sensor platform for EOS HA integration."""
from __future__ import annotations

from homeassistant.components.binary_sensor import (
    BinarySensorEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import EOSCoordinator


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up EOS HA binary sensors from a config entry."""
    coordinator: EOSCoordinator = config_entry.runtime_data
    async_add_entities([EOSDischargeAllowedSensor(coordinator)])


class EOSDischargeAllowedSensor(CoordinatorEntity, BinarySensorEntity):
    """Binary sensor indicating whether battery discharge is currently allowed."""

    def __init__(self, coordinator: EOSCoordinator) -> None:
        """Initialize the discharge allowed sensor."""
        super().__init__(coordinator)
        self._attr_unique_id = (
            f"{coordinator.config_entry.entry_id}_discharge_allowed"
        )
        self._attr_has_entity_name = True
        self._attr_translation_key = "discharge_allowed"
        self._attr_icon = "mdi:battery-arrow-down"
        self._attr_device_info = {
            "identifiers": {(DOMAIN, coordinator.config_entry.entry_id)},
            "name": "EOS",
            "manufacturer": "Akkudoktor",
        }
        # No device_class - this is a custom operational state

    @property
    def is_on(self) -> bool | None:
        """Return True if discharge is allowed for current hour."""
        if not self.coordinator.data:
            return None
        discharge = self.coordinator.data.get("discharge_allowed", [])
        if not discharge:
            return None
        return bool(discharge[0])

    @property
    def extra_state_attributes(self) -> dict[str, any]:
        """Return the full 48h discharge schedule."""
        if not self.coordinator.data:
            return {}
        return {
            "forecast": self.coordinator.data.get("discharge_allowed", []),
        }
