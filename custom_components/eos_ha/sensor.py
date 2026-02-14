"""Sensor platform for EOS HA integration."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import UnitOfEnergy, UnitOfPower
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import CONF_EOS_URL, DEFAULT_SCAN_INTERVAL, DOMAIN
from .coordinator import EOSCoordinator


@dataclass(frozen=True, kw_only=True)
class EOSSensorEntityDescription(SensorEntityDescription):
    """Describe an EOS sensor."""

    value_fn: Callable[[dict[str, Any]], Any] = None
    attrs_fn: Callable[[dict[str, Any]], dict[str, Any]] | None = None


def _current_hour_value(data: dict, key: str) -> float | None:
    """Get current hour value (index 0) from a 48h array."""
    arr = data.get(key, [])
    return round(arr[0], 2) if arr else None


def _derive_mode(data: dict) -> str:
    """Derive current operating mode from optimization data.

    If a manual override is active, it takes priority.
    """
    override = data.get("active_override")
    if override == "charge":
        return "Override: Charge"
    if override == "discharge":
        return "Override: Discharge"

    ac = data.get("ac_charge", [])
    discharge = data.get("discharge_allowed", [])
    if ac and ac[0] > 0:
        return "Grid Charge"
    if discharge and discharge[0] == 0:
        return "Avoid Discharge"
    return "Allow Discharge"


SENSOR_DESCRIPTIONS: tuple[EOSSensorEntityDescription, ...] = (
    EOSSensorEntityDescription(
        key="ac_charge_power",
        translation_key="ac_charge_power",
        native_unit_of_measurement=UnitOfPower.WATT,
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        icon="mdi:battery-charging",
        value_fn=lambda d: _current_hour_value(d, "ac_charge"),
        attrs_fn=lambda d: {"forecast": d.get("ac_charge", [])},
    ),
    EOSSensorEntityDescription(
        key="dc_charge_power",
        translation_key="dc_charge_power",
        native_unit_of_measurement=UnitOfPower.WATT,
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        icon="mdi:solar-power",
        value_fn=lambda d: _current_hour_value(d, "dc_charge"),
        attrs_fn=lambda d: {"forecast": d.get("dc_charge", [])},
    ),
    EOSSensorEntityDescription(
        key="current_mode",
        translation_key="current_mode",
        icon="mdi:auto-fix",
        value_fn=_derive_mode,
    ),
    EOSSensorEntityDescription(
        key="pv_forecast",
        translation_key="pv_forecast",
        native_unit_of_measurement=UnitOfPower.WATT,
        device_class=SensorDeviceClass.POWER,
        icon="mdi:solar-panel-large",
        value_fn=lambda d: _current_hour_value(d, "pv_forecast"),
        attrs_fn=lambda d: {"forecast": d.get("pv_forecast", [])},
    ),
    EOSSensorEntityDescription(
        key="price_forecast",
        translation_key="price_forecast",
        native_unit_of_measurement="EUR/Wh",
        icon="mdi:currency-eur",
        value_fn=lambda d: _current_hour_value(d, "price_forecast"),
        attrs_fn=lambda d: {"forecast": d.get("price_forecast", [])},
    ),
    EOSSensorEntityDescription(
        key="consumption_forecast",
        translation_key="consumption_forecast",
        native_unit_of_measurement=UnitOfPower.WATT,
        device_class=SensorDeviceClass.POWER,
        icon="mdi:home-lightning-bolt",
        value_fn=lambda d: _current_hour_value(d, "consumption_forecast"),
        attrs_fn=lambda d: {"forecast": d.get("consumption_forecast", [])},
    ),
    EOSSensorEntityDescription(
        key="battery_soc_forecast",
        translation_key="battery_soc_forecast",
        native_unit_of_measurement="%",
        device_class=SensorDeviceClass.BATTERY,
        icon="mdi:battery",
        value_fn=lambda d: _current_hour_value(d, "battery_soc_forecast"),
        attrs_fn=lambda d: {"forecast": d.get("battery_soc_forecast", [])},
    ),
    EOSSensorEntityDescription(
        key="override_status",
        translation_key="override_status",
        icon="mdi:hand-back-right",
        value_fn=lambda d: d.get("active_override", "none") or "none",
    ),
    EOSSensorEntityDescription(
        key="total_cost",
        translation_key="total_cost",
        native_unit_of_measurement="EUR",
        device_class=SensorDeviceClass.MONETARY,
        state_class=SensorStateClass.TOTAL,
        icon="mdi:cash",
        value_fn=lambda d: round(d["total_cost"], 2) if d.get("total_cost") is not None else None,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up EOS HA sensors from a config entry."""
    coordinator: EOSCoordinator = hass.data[DOMAIN][config_entry.entry_id]

    entities: list[SensorEntity] = [EOSOptimizationStatusSensor(coordinator)]
    entities.extend(
        EOSSensor(coordinator, description) for description in SENSOR_DESCRIPTIONS
    )
    async_add_entities(entities)


class EOSSensor(CoordinatorEntity, SensorEntity):
    """Generic EOS sensor driven by entity description."""

    entity_description: EOSSensorEntityDescription

    def __init__(
        self,
        coordinator: EOSCoordinator,
        description: EOSSensorEntityDescription,
    ) -> None:
        """Initialize."""
        super().__init__(coordinator)
        self.entity_description = description
        self._attr_unique_id = f"{coordinator.config_entry.entry_id}_{description.key}"
        self._attr_has_entity_name = True
        self._attr_device_info = {
            "identifiers": {(DOMAIN, coordinator.config_entry.entry_id)},
            "name": "EOS Energy Optimizer",
            "manufacturer": "Akkudoktor",
        }

    @property
    def native_value(self) -> Any:
        """Return sensor value."""
        if not self.coordinator.data:
            return None
        return self.entity_description.value_fn(self.coordinator.data)

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        """Return extra attributes."""
        if not self.coordinator.data or not self.entity_description.attrs_fn:
            return None
        return self.entity_description.attrs_fn(self.coordinator.data)


class EOSOptimizationStatusSensor(CoordinatorEntity, SensorEntity):
    """Sensor showing EOS optimization status and health."""

    def __init__(self, coordinator: EOSCoordinator) -> None:
        """Initialize the optimization status sensor."""
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.config_entry.entry_id}_optimization_status"
        self._attr_name = "EOS Optimization Status"
        self._attr_icon = "mdi:chart-timeline-variant"
        self._attr_has_entity_name = True
        self._attr_device_info = {
            "identifiers": {(DOMAIN, coordinator.config_entry.entry_id)},
            "name": "EOS Energy Optimizer",
            "manufacturer": "Akkudoktor",
        }

    @property
    def native_value(self) -> str:
        """Return the state of the sensor."""
        if self.coordinator.data and self.coordinator.data.get("last_success"):
            return "optimized"
        if self.coordinator.last_update_success is False:
            return "failed"
        return "unknown"

    @property
    def extra_state_attributes(self) -> dict[str, any]:
        """Return additional state attributes."""
        attrs = {
            "eos_server_url": self.coordinator.config_entry.data.get(CONF_EOS_URL),
            "update_interval_seconds": DEFAULT_SCAN_INTERVAL,
        }
        if self.coordinator.data:
            attrs["last_update"] = self.coordinator.data.get("last_update")
            attrs["last_success"] = self.coordinator.data.get("last_success")
        else:
            attrs["last_update"] = None
            attrs["last_success"] = None
        return attrs
