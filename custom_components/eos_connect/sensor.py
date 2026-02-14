"""Sensor platform for EOS Connect integration."""
from __future__ import annotations

from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import CONF_EOS_URL, DEFAULT_SCAN_INTERVAL, DOMAIN
from .coordinator import EOSCoordinator


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up EOS Connect sensor from a config entry."""
    coordinator: EOSCoordinator = hass.data[DOMAIN][config_entry.entry_id]

    # Create optimization status sensor
    async_add_entities([EOSOptimizationStatusSensor(coordinator)])


class EOSOptimizationStatusSensor(CoordinatorEntity, SensorEntity):
    """Sensor showing EOS optimization status and health."""

    def __init__(self, coordinator: EOSCoordinator) -> None:
        """Initialize the optimization status sensor.

        Args:
            coordinator: EOSCoordinator instance
        """
        super().__init__(coordinator)

        self._attr_unique_id = f"{coordinator.config_entry.entry_id}_optimization_status"
        self._attr_name = "EOS Optimization Status"
        self._attr_icon = "mdi:chart-timeline-variant"

    @property
    def native_value(self) -> str:
        """Return the state of the sensor.

        Returns:
            "optimized" if last run succeeded
            "failed" if last run failed
            "unknown" if no data yet
        """
        if self.coordinator.data and self.coordinator.data.get("last_success"):
            return "optimized"
        if self.coordinator.last_update_success is False:
            return "failed"
        return "unknown"

    @property
    def extra_state_attributes(self) -> dict[str, any]:
        """Return additional state attributes.

        Returns:
            Dict with last_update timestamp, success status, server URL, and update interval
        """
        attrs = {
            "eos_server_url": self.coordinator.config_entry.data.get(CONF_EOS_URL),
            "update_interval_seconds": DEFAULT_SCAN_INTERVAL,
        }

        # Add data from coordinator if available
        if self.coordinator.data:
            attrs["last_update"] = self.coordinator.data.get("last_update")
            attrs["last_success"] = self.coordinator.data.get("last_success")
        else:
            attrs["last_update"] = None
            attrs["last_success"] = None

        return attrs
