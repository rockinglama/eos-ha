"""Number entities for EOS HA integration."""
from __future__ import annotations

from dataclasses import dataclass
import logging

from homeassistant.components.number import (
    NumberDeviceClass,
    NumberEntity,
    NumberEntityDescription,
    NumberMode,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import UnitOfEnergy, UnitOfPower, PERCENTAGE
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import (
    CONF_BATTERY_CAPACITY,
    CONF_INVERTER_POWER,
    CONF_MAX_CHARGE_POWER,
    CONF_MAX_SOC,
    CONF_MIN_SOC,
    DEFAULT_BATTERY_CAPACITY,
    DEFAULT_INVERTER_POWER,
    DEFAULT_MAX_CHARGE_POWER,
    DEFAULT_MAX_SOC,
    DEFAULT_MIN_SOC,
    DOMAIN,
)
from .coordinator import EOSCoordinator

_LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True, kw_only=True)
class EOSNumberEntityDescription(NumberEntityDescription):
    """Describe an EOS number entity."""

    config_key: str


NUMBERS: tuple[EOSNumberEntityDescription, ...] = (
    EOSNumberEntityDescription(
        key="battery_capacity",
        translation_key="battery_capacity",
        name="Battery Capacity",
        icon="mdi:battery-high",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=NumberDeviceClass.ENERGY,
        native_min_value=0.1,
        native_max_value=100.0,
        native_step=0.1,
        mode=NumberMode.BOX,
        config_key=CONF_BATTERY_CAPACITY,
    ),
    EOSNumberEntityDescription(
        key="max_charge_power",
        translation_key="max_charge_power",
        name="Max Charge Power",
        icon="mdi:flash",
        native_unit_of_measurement=UnitOfPower.WATT,
        device_class=NumberDeviceClass.POWER,
        native_min_value=100,
        native_max_value=50000,
        native_step=100,
        mode=NumberMode.BOX,
        config_key=CONF_MAX_CHARGE_POWER,
    ),
    EOSNumberEntityDescription(
        key="inverter_power",
        translation_key="inverter_power",
        name="Inverter Power",
        icon="mdi:solar-power",
        native_unit_of_measurement=UnitOfPower.WATT,
        device_class=NumberDeviceClass.POWER,
        native_min_value=100,
        native_max_value=50000,
        native_step=100,
        mode=NumberMode.BOX,
        config_key=CONF_INVERTER_POWER,
    ),
    EOSNumberEntityDescription(
        key="min_soc",
        translation_key="min_soc",
        name="Minimum SOC",
        icon="mdi:battery-low",
        native_unit_of_measurement=PERCENTAGE,
        native_min_value=0,
        native_max_value=100,
        native_step=1,
        mode=NumberMode.SLIDER,
        config_key=CONF_MIN_SOC,
    ),
    EOSNumberEntityDescription(
        key="max_soc",
        translation_key="max_soc",
        name="Maximum SOC",
        icon="mdi:battery-charging-100",
        native_unit_of_measurement=PERCENTAGE,
        native_min_value=0,
        native_max_value=100,
        native_step=1,
        mode=NumberMode.SLIDER,
        config_key=CONF_MAX_SOC,
    ),
)

# Map config keys to defaults
_DEFAULTS = {
    CONF_BATTERY_CAPACITY: DEFAULT_BATTERY_CAPACITY,
    CONF_MAX_CHARGE_POWER: DEFAULT_MAX_CHARGE_POWER,
    CONF_INVERTER_POWER: DEFAULT_INVERTER_POWER,
    CONF_MIN_SOC: DEFAULT_MIN_SOC,
    CONF_MAX_SOC: DEFAULT_MAX_SOC,
}


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up EOS number entities from a config entry."""
    coordinator: EOSCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(
        EOSNumber(coordinator, entry, description) for description in NUMBERS
    )


class EOSNumber(NumberEntity):
    """EOS Number entity — writes to config entry options."""

    entity_description: EOSNumberEntityDescription
    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: EOSCoordinator,
        entry: ConfigEntry,
        description: EOSNumberEntityDescription,
    ) -> None:
        """Initialize the number entity."""
        self.entity_description = description
        self._coordinator = coordinator
        self._entry = entry
        self._attr_unique_id = f"{entry.entry_id}_{description.key}"
        self._attr_device_info = {
            "identifiers": {(DOMAIN, entry.entry_id)},
            "name": "EOS Energy Optimizer",
            "manufacturer": "Akkudoktor",
        }

    @property
    def native_value(self) -> float | None:
        """Return current value from options (runtime) or data (setup)."""
        key = self.entity_description.config_key
        return self._entry.options.get(
            key,
            self._entry.data.get(key, _DEFAULTS.get(key)),
        )

    async def async_set_native_value(self, value: float) -> None:
        """Update value by writing to config entry options."""
        key = self.entity_description.config_key
        new_options = {**self._entry.options, key: value}
        self.hass.config_entries.async_update_entry(self._entry, options=new_options)
        # Trigger a refresh so the new value takes effect next cycle
        await self._coordinator.async_request_refresh()
