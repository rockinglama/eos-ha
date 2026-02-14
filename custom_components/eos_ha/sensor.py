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
from homeassistant.const import UnitOfPower
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from homeassistant.helpers.event import async_track_state_change_event
from homeassistant.helpers.restore_state import RestoreEntity

from .const import (
    CONF_BATTERY_ENERGY,
    CONF_BATTERY_GRID_POWER,
    CONF_BATTERY_PV_POWER,
    CONF_EOS_URL,
    CONF_SG_READY_ENABLED,
    DEFAULT_BATTERY_EFFICIENCY,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
    CONF_BATTERY_CAPACITY,
    CONF_MAX_SOC,
    CONF_MIN_SOC,
    CONF_PRICE_SOURCE,
    CONF_PRICE_ENTITY,
    DEFAULT_BATTERY_CAPACITY,
    DEFAULT_MAX_SOC,
    DEFAULT_MIN_SOC,
    PRICE_SOURCE_EXTERNAL,
    SG_READY_MODES,
)
from .coordinator import EOSCoordinator

import logging

_LOGGER = logging.getLogger(__name__)

PARALLEL_UPDATES = 1


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
    """Derive current operating mode from optimization data."""
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


def _energy_plan_mode(data: dict) -> str | None:
    """Get current operation mode from energy plan."""
    plan = data.get("energy_plan", {})
    instructions = plan.get("instructions", [])
    if not instructions:
        return None
    # The last instruction before now is the active one
    return instructions[0].get("operation_mode_id", "unknown")


def _price_forecast_attrs(data: dict) -> dict[str, Any]:
    """Build enhanced price forecast attributes."""
    forecast = data.get("price_forecast", [])
    attrs: dict[str, Any] = {"forecast": forecast}
    if forecast:
        avg = sum(forecast) / len(forecast)
        current = forecast[0] if forecast else 0
        attrs["price_below_average"] = current < avg
        # Find 5 cheapest upcoming hours (index, price)
        indexed = [(i, p) for i, p in enumerate(forecast)]
        indexed.sort(key=lambda x: x[1])
        attrs["cheapest_hours"] = [{"hour": i, "price": round(p, 6)} for i, p in indexed[:5]]
    return attrs


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
        attrs_fn=lambda d: _price_forecast_attrs(d),
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
    EOSSensorEntityDescription(
        key="energy_plan",
        translation_key="energy_plan",
        icon="mdi:calendar-clock",
        value_fn=_energy_plan_mode,
        attrs_fn=lambda d: {
            "plan_id": d.get("energy_plan", {}).get("id"),
            "generated_at": d.get("energy_plan", {}).get("generated_at"),
            "valid_from": d.get("energy_plan", {}).get("valid_from"),
            "valid_until": d.get("energy_plan", {}).get("valid_until"),
            "instructions": d.get("energy_plan", {}).get("instructions", []),
        },
    ),
    EOSSensorEntityDescription(
        key="ev_charge_plan",
        translation_key="ev_charge_plan",
        icon="mdi:car-electric",
        value_fn=lambda d: "active" if d.get("ev_charge_plan") else "inactive",
        attrs_fn=lambda d: d.get("ev_charge_plan", {}),
    ),
    EOSSensorEntityDescription(
        key="appliance_schedule",
        translation_key="appliance_schedule",
        icon="mdi:water-boiler",
        value_fn=lambda d: str(len(d.get("appliance_schedules", {}))) + " appliances" if d.get("appliance_schedules") else "none",
        attrs_fn=lambda d: {"schedules": d.get("appliance_schedules", {})},
    ),
    EOSSensorEntityDescription(
        key="resource_status",
        translation_key="resource_status",
        icon="mdi:battery-heart-variant",
        value_fn=lambda d: "available" if d.get("resource_status") else "unavailable",
        attrs_fn=lambda d: d.get("resource_status", {}),
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up EOS HA sensors from a config entry."""
    coordinator: EOSCoordinator = config_entry.runtime_data

    entities: list[SensorEntity] = [EOSOptimizationStatusSensor(coordinator)]
    entities.extend(
        EOSSensor(coordinator, description) for description in SENSOR_DESCRIPTIONS
    )

    # Battery Storage Price Sensor — only if battery_energy_entity is configured
    current = {**config_entry.data, **config_entry.options}
    if current.get(CONF_BATTERY_ENERGY):
        entities.append(EOSBatteryStoragePriceSensor(coordinator, current))

    # SG-Ready Mode Sensor — only if SG-Ready is enabled
    if current.get(CONF_SG_READY_ENABLED, False):
        entities.append(EOSSGReadyModeSensor(coordinator, current))

    async_add_entities(entities)


class EOSSensor(CoordinatorEntity, SensorEntity):
    """Generic EOS sensor driven by entity description."""

    entity_description: EOSSensorEntityDescription

    def __init__(
        self,
        coordinator: EOSCoordinator,
        description: EOSSensorEntityDescription,
    ) -> None:
        super().__init__(coordinator)
        self.entity_description = description
        self._attr_unique_id = f"{coordinator.config_entry.entry_id}_{description.key}"
        self._attr_has_entity_name = True
        self._attr_device_info = {
            "identifiers": {(DOMAIN, coordinator.config_entry.entry_id)},
            "name": "EOS",
            "manufacturer": "Akkudoktor",
        }

    @property
    def native_value(self) -> Any:
        if not self.coordinator.data:
            return None
        return self.entity_description.value_fn(self.coordinator.data)

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        if not self.coordinator.data or not self.entity_description.attrs_fn:
            return None
        return self.entity_description.attrs_fn(self.coordinator.data)


class EOSOptimizationStatusSensor(CoordinatorEntity, SensorEntity):
    """Sensor showing EOS optimization status and health."""

    def __init__(self, coordinator: EOSCoordinator) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.config_entry.entry_id}_optimization_status"
        self._attr_name = "Optimization Status"
        self._attr_icon = "mdi:chart-timeline-variant"
        self._attr_has_entity_name = True
        self._attr_device_info = {
            "identifiers": {(DOMAIN, coordinator.config_entry.entry_id)},
            "name": "EOS",
            "manufacturer": "Akkudoktor",
        }

    @property
    def native_value(self) -> str:
        if self.coordinator.data and self.coordinator.data.get("last_success"):
            return "optimized"
        if self.coordinator.last_update_success is False:
            return "failed"
        return "unknown"

    @property
    def extra_state_attributes(self) -> dict[str, any]:
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
        # Add optimization error info
        if self.coordinator.last_exception:
            attrs["optimization_error"] = str(self.coordinator.last_exception)
        else:
            attrs["optimization_error"] = None
        return attrs


class EOSBatteryStoragePriceSensor(RestoreEntity, SensorEntity):
    """Tracks the weighted average price of energy stored in the battery (€/kWh)."""

    def __init__(self, coordinator: EOSCoordinator, config: dict[str, Any]) -> None:
        self._coordinator = coordinator
        self._config = config
        self._attr_unique_id = f"{coordinator.config_entry.entry_id}_battery_storage_price"
        self._attr_has_entity_name = True
        self._attr_name = "Battery Storage Price"
        self._attr_icon = "mdi:battery-charging-high"
        self._attr_native_unit_of_measurement = "EUR/kWh"
        self._attr_device_class = SensorDeviceClass.MONETARY
        self._attr_state_class = SensorStateClass.MEASUREMENT
        self._attr_device_info = {
            "identifiers": {(DOMAIN, coordinator.config_entry.entry_id)},
            "name": "EOS",
            "manufacturer": "Akkudoktor",
        }

        self._price: float = 0.0
        self._circulating_energy: float = 0.0
        self._total_value: float = 0.0
        self._last_energy: float | None = None
        self._unsub_listeners: list = []

        # Config values
        self._energy_entity = config.get(CONF_BATTERY_ENERGY, "")
        self._grid_power_entity = config.get(CONF_BATTERY_GRID_POWER, "")
        self._pv_power_entity = config.get(CONF_BATTERY_PV_POWER, "")
        self._efficiency = DEFAULT_BATTERY_EFFICIENCY

    def _get_battery_capacity(self) -> float:
        current = {**self._coordinator.config_entry.data, **self._coordinator.config_entry.options}
        return float(current.get(CONF_BATTERY_CAPACITY, DEFAULT_BATTERY_CAPACITY))

    def _get_min_soc(self) -> float:
        current = {**self._coordinator.config_entry.data, **self._coordinator.config_entry.options}
        return float(current.get(CONF_MIN_SOC, DEFAULT_MIN_SOC))

    def _get_energy_floor(self) -> float:
        return (self._get_min_soc() / 100.0) * self._get_battery_capacity()

    def _get_current_grid_price(self) -> float:
        """Get current electricity price in EUR/kWh."""
        current = {**self._coordinator.config_entry.data, **self._coordinator.config_entry.options}
        price_source = current.get(CONF_PRICE_SOURCE, "")

        if price_source == PRICE_SOURCE_EXTERNAL:
            price_entity = current.get(CONF_PRICE_ENTITY, "")
            if price_entity:
                state = self.hass.states.get(price_entity)
                if state and state.state not in ("unknown", "unavailable"):
                    try:
                        return float(state.state)
                    except (ValueError, TypeError):
                        pass
            return 0.0

        # From coordinator forecast — price_forecast is in EUR/Wh
        if self._coordinator.data:
            forecast = self._coordinator.data.get("price_forecast", [])
            if forecast:
                return float(forecast[0]) * 1000.0  # EUR/Wh → EUR/kWh
        return 0.0

    def _get_entity_value(self, entity_id: str) -> float | None:
        if not entity_id:
            return None
        state = self.hass.states.get(entity_id)
        if state and state.state not in ("unknown", "unavailable"):
            try:
                return float(state.state)
            except (ValueError, TypeError):
                return None
        return None

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()

        # Restore state
        old_state = await self.async_get_last_state()
        if old_state and old_state.state not in ("unknown", "unavailable"):
            try:
                self._price = float(old_state.state)
                self._circulating_energy = float(old_state.attributes.get("circulating_energy_kwh", 0))
                self._total_value = float(old_state.attributes.get("total_value_eur", 0))
            except (ValueError, TypeError):
                pass

        # Track state changes on input entities
        entities_to_track = [e for e in [self._energy_entity, self._grid_power_entity, self._pv_power_entity] if e]
        if entities_to_track:
            self._unsub_listeners.append(
                async_track_state_change_event(self.hass, entities_to_track, self._async_state_changed)
            )

    async def async_will_remove_from_hass(self) -> None:
        for unsub in self._unsub_listeners:
            unsub()
        self._unsub_listeners.clear()

    async def _async_state_changed(self, event) -> None:
        """Handle state change of tracked entities."""
        self._update_price()
        self.async_write_ha_state()

    def _update_price(self) -> None:
        """Recalculate the storage price based on current entity states."""
        current_energy = self._get_entity_value(self._energy_entity)
        if current_energy is None:
            return

        energy_floor = self._get_energy_floor()
        circulating = max(0.0, current_energy - energy_floor)

        # Battery empty
        if circulating < 0.01:
            self._price = 0.0
            self._circulating_energy = 0.0
            self._total_value = 0.0
            self._last_energy = current_energy
            return

        grid_power = self._get_entity_value(self._grid_power_entity) or 0.0
        pv_power = self._get_entity_value(self._pv_power_entity) or 0.0
        total_power = grid_power + pv_power

        # Charging (total_power > 10W)
        if total_power > 10.0 and self._last_energy is not None:
            energy_delta = current_energy - self._last_energy

            if energy_delta > 0.001:  # Actually gained energy
                # Split into grid/PV based on power ratio
                if total_power > 0:
                    grid_ratio = grid_power / total_power
                else:
                    grid_ratio = 0.5

                grid_kwh = energy_delta * grid_ratio

                grid_price = self._get_current_grid_price()
                cost_new = grid_kwh * grid_price * (1.0 / self._efficiency)
                # PV cost is 0

                new_total_value = self._total_value + cost_new
                new_circulating = circulating

                if new_circulating > 0.01:
                    self._price = round(new_total_value / new_circulating, 4)
                    self._total_value = new_total_value
                    self._circulating_energy = new_circulating
                else:
                    self._price = 0.0
                    self._total_value = 0.0
                    self._circulating_energy = 0.0
            else:
                # Discharging or no change — hold price, update circulating
                self._circulating_energy = circulating
                if circulating > 0.01:
                    self._total_value = self._price * circulating
        else:
            # Not charging or first reading — hold price, update circulating
            self._circulating_energy = circulating
            if self._last_energy is None and circulating > 0.01 and self._price > 0:
                # Restored state — recalculate total_value from price × circulating
                self._total_value = self._price * circulating

        self._last_energy = current_energy

    @property
    def native_value(self) -> float:
        return round(self._price, 4)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        return {
            "circulating_energy_kwh": round(self._circulating_energy, 3),
            "total_value_eur": round(self._total_value, 4),
            "efficiency_rate": self._efficiency,
            "energy_floor_kwh": round(self._get_energy_floor(), 3),
        }


class EOSSGReadyModeSensor(CoordinatorEntity, SensorEntity):
    """Sensor that recommends an SG-Ready mode (1-4) based on optimization data."""

    def __init__(self, coordinator: EOSCoordinator, config: dict[str, Any]) -> None:
        super().__init__(coordinator)
        self._config = config
        self._attr_unique_id = f"{coordinator.config_entry.entry_id}_sg_ready_mode"
        self._attr_has_entity_name = True
        self._attr_name = "SG Ready Mode"
        self._attr_icon = "mdi:heat-pump"
        self._attr_device_info = {
            "identifiers": {(DOMAIN, coordinator.config_entry.entry_id)},
            "name": "EOS",
            "manufacturer": "Akkudoktor",
        }

    def _get_config(self) -> dict[str, Any]:
        return {**self.coordinator.config_entry.data, **self.coordinator.config_entry.options}

    def _compute_mode(self) -> tuple[int, str]:
        """Compute recommended SG-Ready mode and reason."""
        # Check for manual override first
        override = self.coordinator.sg_ready_override
        if override is not None:
            return override, f"Manual override (mode {override})"

        data = self.coordinator.data
        if not data:
            return 2, "No optimization data"

        config = self._get_config()
        max_soc = float(config.get(CONF_MAX_SOC, DEFAULT_MAX_SOC))
        min_soc = float(config.get(CONF_MIN_SOC, DEFAULT_MIN_SOC))

        # Current values from forecasts (index 0)
        pv_forecast = data.get("pv_forecast", [])
        price_forecast = data.get("price_forecast", [])
        soc_forecast = data.get("battery_soc_forecast", [])
        consumption_forecast = data.get("consumption_forecast", [])

        current_pv = pv_forecast[0] if pv_forecast else 0
        current_price = price_forecast[0] if price_forecast else 0
        current_soc = soc_forecast[0] if soc_forecast else 50
        current_consumption = consumption_forecast[0] if consumption_forecast else 0

        # Daily average price
        avg_price = sum(price_forecast[:24]) / len(price_forecast[:24]) if price_forecast else current_price

        pv_surplus = current_pv - current_consumption if current_pv and current_consumption else 0

        # Mode 4: Force — significant PV surplus AND battery full
        if pv_surplus > 500 and current_soc > (max_soc - 5):
            return 4, f"PV surplus ({pv_surplus:.0f}W) and battery full ({current_soc:.0f}%)"

        # Mode 3: Recommend — PV surplus OR cheap electricity
        if pv_surplus > 200:
            return 3, f"PV surplus available ({pv_surplus:.0f}W)"
        if avg_price > 0 and current_price < avg_price * 0.5:
            return 3, f"Cheap electricity ({current_price:.4f} < 50% avg {avg_price:.4f})"

        # Mode 1: Lock — expensive power, no PV, low battery
        if avg_price > 0 and current_price > avg_price * 1.5 and current_pv < 100 and current_soc < (min_soc + 10):
            return 1, f"Expensive ({current_price:.4f} > 150% avg), no PV, low SOC ({current_soc:.0f}%)"

        # Mode 2: Normal
        return 2, "Normal operation"

    @property
    def native_value(self) -> int:
        mode, _ = self._compute_mode()
        return mode

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        mode, reason = self._compute_mode()
        return {
            "mode_name": SG_READY_MODES.get(mode, "Unknown"),
            "reason": reason,
        }
