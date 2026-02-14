"""The EOS HA integration."""
from __future__ import annotations

import logging

import voluptuous as vol

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError

from .const import DOMAIN
from .coordinator import EOSCoordinator

_LOGGER = logging.getLogger(__name__)

PLATFORMS = ["sensor", "binary_sensor", "number", "switch", "button"]

type EosHaConfigEntry = ConfigEntry[EOSCoordinator]


async def async_setup_entry(hass: HomeAssistant, entry: EosHaConfigEntry) -> bool:
    """Set up EOS HA from a config entry."""
    coordinator = EOSCoordinator(hass, entry)

    # Perform initial data fetch - raises ConfigEntryNotReady on failure
    await coordinator.async_config_entry_first_refresh()

    # Store coordinator in runtime_data
    entry.runtime_data = coordinator

    # Forward setup to platforms
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    # Listen for options updates
    entry.async_on_unload(entry.add_update_listener(_async_update_listener))

    # Register services
    _register_services(hass)

    return True


async def _async_update_listener(hass: HomeAssistant, entry: EosHaConfigEntry) -> None:
    """Handle options update — reload the integration."""
    await hass.config_entries.async_reload(entry.entry_id)


def _register_services(hass: HomeAssistant) -> None:
    """Register EOS HA services (idempotent)."""

    def _get_coordinators() -> list[EOSCoordinator]:
        """Get all active coordinators from config entries."""
        return [
            entry.runtime_data
            for entry in hass.config_entries.async_entries(DOMAIN)
            if hasattr(entry, "runtime_data") and entry.runtime_data is not None
        ]

    async def handle_optimize_now(call: ServiceCall) -> None:
        """Handle optimize_now service call — trigger prediction update then fetch solution."""
        coordinators = _get_coordinators()
        if not coordinators:
            raise HomeAssistantError("No EOS HA instances configured")
        for coordinator in coordinators:
            try:
                _LOGGER.info("Manual optimization triggered via service call")
                # Trigger EOS to update predictions (which triggers re-optimization)
                await coordinator.eos_client.update_predictions(force_update=True)
                # Then refresh our data from the new solution
                await coordinator.async_request_refresh()
            except Exception as err:
                raise HomeAssistantError(
                    f"Failed to trigger optimization: {err}"
                ) from err

    async def handle_set_override(call: ServiceCall) -> None:
        """Handle set_override service call."""
        mode = call.data.get("mode")
        if mode is None:
            raise ServiceValidationError("Mode is required")
        duration = call.data.get("duration", 60)
        coordinators = _get_coordinators()
        if not coordinators:
            raise HomeAssistantError("No EOS HA instances configured")
        for coordinator in coordinators:
            try:
                coordinator.set_override(mode, duration)
                _LOGGER.info("Override set: mode=%s, duration=%s min", mode, duration)
                await coordinator.async_request_refresh()
            except Exception as err:
                raise HomeAssistantError(
                    f"Failed to set override: {err}"
                ) from err

    async def handle_update_predictions(call: ServiceCall) -> None:
        """Handle update_predictions service call — triggers EOS prediction recalculation."""
        coordinators = _get_coordinators()
        if not coordinators:
            raise HomeAssistantError("No EOS HA instances configured")
        for coordinator in coordinators:
            try:
                _LOGGER.info("Triggering EOS prediction update via service call")
                success = await coordinator.eos_client.update_predictions(force_update=True)
                if success:
                    _LOGGER.info("EOS predictions updated, triggering optimization refresh")
                    await coordinator.async_request_refresh()
                else:
                    raise HomeAssistantError("EOS prediction update returned failure")
            except HomeAssistantError:
                raise
            except Exception as err:
                raise HomeAssistantError(
                    f"Failed to update predictions: {err}"
                ) from err

    if not hass.services.has_service(DOMAIN, "optimize_now"):
        hass.services.async_register(
            DOMAIN,
            "optimize_now",
            handle_optimize_now,
            schema=vol.Schema({}),
        )

    if not hass.services.has_service(DOMAIN, "set_override"):
        hass.services.async_register(
            DOMAIN,
            "set_override",
            handle_set_override,
            schema=vol.Schema(
                {
                    vol.Required("mode"): vol.In(
                        ["charge", "discharge", "auto"]
                    ),
                    vol.Optional("duration", default=60): vol.All(
                        vol.Coerce(int), vol.Range(min=1, max=1440)
                    ),
                }
            ),
        )

    async def handle_set_sg_ready_mode(call: ServiceCall) -> None:
        """Handle set_sg_ready_mode service call."""
        mode = call.data.get("mode")
        if mode is None or mode not in (1, 2, 3, 4):
            raise ServiceValidationError("Mode must be 1-4")
        duration = call.data.get("duration", 60)
        coordinators = _get_coordinators()
        if not coordinators:
            raise HomeAssistantError("No EOS HA instances configured")
        for coordinator in coordinators:
            try:
                coordinator.set_sg_ready_override(mode, duration)
                _LOGGER.info("SG-Ready override set: mode=%s, duration=%s min", mode, duration)
                coordinator.async_set_updated_data(coordinator.data)
            except Exception as err:
                raise HomeAssistantError(
                    f"Failed to set SG-Ready mode: {err}"
                ) from err

    if not hass.services.has_service(DOMAIN, "set_sg_ready_mode"):
        hass.services.async_register(
            DOMAIN,
            "set_sg_ready_mode",
            handle_set_sg_ready_mode,
            schema=vol.Schema(
                {
                    vol.Required("mode"): vol.All(
                        vol.Coerce(int), vol.Range(min=1, max=4)
                    ),
                    vol.Optional("duration", default=60): vol.All(
                        vol.Coerce(int), vol.Range(min=0, max=1440)
                    ),
                }
            ),
        )

    if not hass.services.has_service(DOMAIN, "update_predictions"):
        hass.services.async_register(
            DOMAIN,
            "update_predictions",
            handle_update_predictions,
            schema=vol.Schema({}),
        )

    async def handle_reset_battery_price(call: ServiceCall) -> None:
        """Handle reset_battery_price service call."""
        hass.data.setdefault(DOMAIN, {})
        sensors = hass.data[DOMAIN].get("battery_price_sensors", [])
        if not sensors:
            _LOGGER.warning("No battery storage price sensors found to reset")
            return
        for sensor in sensors:
            sensor.reset_price()
            _LOGGER.info("Battery storage price reset")

    if not hass.services.has_service(DOMAIN, "reset_battery_price"):
        hass.services.async_register(
            DOMAIN,
            "reset_battery_price",
            handle_reset_battery_price,
            schema=vol.Schema({}),
        )


async def async_unload_entry(hass: HomeAssistant, entry: EosHaConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        coordinator: EOSCoordinator = entry.runtime_data
        await coordinator.async_shutdown()

        # Remove services if no more entries
        remaining = [
            e for e in hass.config_entries.async_entries(DOMAIN)
            if e.entry_id != entry.entry_id
        ]
        if not remaining:
            hass.services.async_remove(DOMAIN, "optimize_now")
            hass.services.async_remove(DOMAIN, "set_override")
            hass.services.async_remove(DOMAIN, "set_sg_ready_mode")
            hass.services.async_remove(DOMAIN, "update_predictions")
            hass.services.async_remove(DOMAIN, "reset_battery_price")

    return unload_ok
