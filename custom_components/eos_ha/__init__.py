"""The EOS HA integration."""
from __future__ import annotations

import logging

import voluptuous as vol

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, ServiceCall

from .const import DOMAIN
from .coordinator import EOSCoordinator

_LOGGER = logging.getLogger(__name__)

PLATFORMS = ["sensor", "binary_sensor", "number"]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up EOS HA from a config entry."""
    coordinator = EOSCoordinator(hass, entry)

    # Perform initial data fetch - raises ConfigEntryNotReady on failure
    await coordinator.async_config_entry_first_refresh()

    # Store coordinator for platform access
    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = coordinator

    # Forward setup to platforms
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    # Listen for options updates
    entry.async_on_unload(entry.add_update_listener(_async_update_listener))

    # Register services
    _register_services(hass)

    return True


async def _async_update_listener(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Handle options update — reload the integration."""
    await hass.config_entries.async_reload(entry.entry_id)


def _register_services(hass: HomeAssistant) -> None:
    """Register EOS HA services (idempotent)."""

    async def handle_optimize_now(call: ServiceCall) -> None:
        """Handle optimize_now service call."""
        for coordinator in hass.data.get(DOMAIN, {}).values():
            _LOGGER.info("Manual optimization triggered via service call")
            await coordinator.async_request_refresh()

    async def handle_set_override(call: ServiceCall) -> None:
        """Handle set_override service call."""
        mode = call.data.get("mode", "auto")
        duration = call.data.get("duration", 60)
        for coordinator in hass.data.get(DOMAIN, {}).values():
            coordinator.set_override(mode, duration)
            _LOGGER.info("Override set: mode=%s, duration=%s min", mode, duration)
            await coordinator.async_request_refresh()

    async def handle_update_predictions(call: ServiceCall) -> None:
        """Handle update_predictions service call — triggers EOS prediction recalculation."""
        for coordinator in hass.data.get(DOMAIN, {}).values():
            _LOGGER.info("Triggering EOS prediction update via service call")
            success = await coordinator.eos_client.update_predictions(force_update=True)
            if success:
                _LOGGER.info("EOS predictions updated, triggering optimization refresh")
                await coordinator.async_request_refresh()
            else:
                _LOGGER.warning("EOS prediction update failed")

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

    if not hass.services.has_service(DOMAIN, "update_predictions"):
        hass.services.async_register(
            DOMAIN,
            "update_predictions",
            handle_update_predictions,
            schema=vol.Schema({}),
        )


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        coordinator: EOSCoordinator = hass.data[DOMAIN].pop(entry.entry_id)
        await coordinator.async_shutdown()

        # Remove services if no more entries
        if not hass.data.get(DOMAIN):
            hass.services.async_remove(DOMAIN, "optimize_now")
            hass.services.async_remove(DOMAIN, "set_override")
            hass.services.async_remove(DOMAIN, "update_predictions")

    return unload_ok
