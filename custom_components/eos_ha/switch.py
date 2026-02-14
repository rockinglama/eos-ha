"""Switch platform for EOS HA integration — SG-Ready auto-control."""
from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import (
    CONF_SG_READY_ENABLED,
    CONF_SG_READY_SWITCH_1,
    CONF_SG_READY_SWITCH_2,
    DOMAIN,
    SG_READY_MODES,
)
from .coordinator import EOSCoordinator

_LOGGER = logging.getLogger(__name__)

# SG-Ready mode → (contact1, contact2) relay states
SG_READY_RELAY_MAP: dict[int, tuple[bool, bool]] = {
    1: (True, False),   # Lock
    2: (False, False),  # Normal
    3: (False, True),   # Recommend
    4: (True, True),    # Force
}


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up EOS HA switches from a config entry."""
    current = {**config_entry.data, **config_entry.options}

    if not current.get(CONF_SG_READY_ENABLED, False):
        return

    coordinator: EOSCoordinator = config_entry.runtime_data
    async_add_entities([EOSSGReadySwitch(coordinator, current)])


class EOSSGReadySwitch(CoordinatorEntity, SwitchEntity):
    """Virtual switch to enable/disable automatic SG-Ready relay control."""

    def __init__(self, coordinator: EOSCoordinator, config: dict[str, Any]) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.config_entry.entry_id}_sg_ready_auto"
        self._attr_has_entity_name = True
        self._attr_name = "SG Ready Auto Control"
        self._attr_icon = "mdi:heat-pump"
        self._attr_device_info = {
            "identifiers": {(DOMAIN, coordinator.config_entry.entry_id)},
            "name": "EOS",
            "manufacturer": "Akkudoktor",
        }

        self._switch_1 = config.get(CONF_SG_READY_SWITCH_1, "")
        self._switch_2 = config.get(CONF_SG_READY_SWITCH_2, "")
        self._is_on = False
        self._last_applied_mode: int | None = None

    @property
    def is_on(self) -> bool:
        return self._is_on

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Enable automatic SG-Ready control."""
        self._is_on = True
        await self._apply_current_mode()
        self.async_write_ha_state()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Disable automatic SG-Ready control — set relays to Normal (mode 2)."""
        self._is_on = False
        self._last_applied_mode = None
        await self._set_relays(2)
        self.async_write_ha_state()

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        if self._is_on:
            self.hass.async_create_task(self._apply_current_mode())
        super()._handle_coordinator_update()

    async def _apply_current_mode(self) -> None:
        """Read recommended mode from the SG-Ready sensor data and apply relays."""
        # Get the recommended mode from the coordinator's SG-Ready sensor logic
        mode = self._compute_recommended_mode()
        if mode != self._last_applied_mode:
            _LOGGER.info("SG-Ready: applying mode %s (%s)", mode, SG_READY_MODES.get(mode))
            await self._set_relays(mode)
            self._last_applied_mode = mode

    def _compute_recommended_mode(self) -> int:
        """Compute the recommended SG-Ready mode (mirrors sensor logic)."""
        # Check override first
        override = self.coordinator.sg_ready_override
        if override is not None:
            return override

        data = self.coordinator.data
        if not data:
            return 2

        config = {**self.coordinator.config_entry.data, **self.coordinator.config_entry.options}
        from .const import CONF_MAX_SOC, CONF_MIN_SOC, DEFAULT_MAX_SOC, DEFAULT_MIN_SOC
        max_soc = float(config.get(CONF_MAX_SOC, DEFAULT_MAX_SOC))
        min_soc = float(config.get(CONF_MIN_SOC, DEFAULT_MIN_SOC))

        pv_forecast = data.get("pv_forecast", [])
        price_forecast = data.get("price_forecast", [])
        soc_forecast = data.get("battery_soc_forecast", [])
        consumption_forecast = data.get("consumption_forecast", [])

        current_pv = pv_forecast[0] if pv_forecast else 0
        current_price = price_forecast[0] if price_forecast else 0
        current_soc = soc_forecast[0] if soc_forecast else 50
        current_consumption = consumption_forecast[0] if consumption_forecast else 0

        avg_price = sum(price_forecast[:24]) / len(price_forecast[:24]) if price_forecast else current_price
        pv_surplus = current_pv - current_consumption if current_pv and current_consumption else 0

        if pv_surplus > 500 and current_soc > (max_soc - 5):
            return 4
        if pv_surplus > 200:
            return 3
        if avg_price > 0 and current_price < avg_price * 0.5:
            return 3
        if avg_price > 0 and current_price > avg_price * 1.5 and current_pv < 100 and current_soc < (min_soc + 10):
            return 1
        return 2

    async def _set_relays(self, mode: int) -> None:
        """Set SG-Ready relay switches to match the given mode."""
        contact1, contact2 = SG_READY_RELAY_MAP.get(mode, (False, False))

        if self._switch_1:
            service = "turn_on" if contact1 else "turn_off"
            await self.hass.services.async_call(
                "homeassistant", service,
                {"entity_id": self._switch_1},
                blocking=True,
            )

        if self._switch_2:
            service = "turn_on" if contact2 else "turn_off"
            await self.hass.services.async_call(
                "homeassistant", service,
                {"entity_id": self._switch_2},
                blocking=True,
            )

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        mode = self._last_applied_mode
        return {
            "current_mode": mode,
            "mode_name": SG_READY_MODES.get(mode, "Unknown") if mode else "Inactive",
            "switch_1_entity": self._switch_1,
            "switch_2_entity": self._switch_2,
        }
