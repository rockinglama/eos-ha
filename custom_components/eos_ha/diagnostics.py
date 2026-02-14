"""Diagnostics support for EOS HA integration."""
from __future__ import annotations

from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .const import DOMAIN
from .coordinator import EOSCoordinator

# Keys to redact from diagnostics output
TO_REDACT = {"latitude", "longitude", "eos_url"}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: ConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    coordinator: EOSCoordinator = hass.data[DOMAIN][entry.entry_id]

    # Build diagnostics data
    diag: dict[str, Any] = {
        "config_entry": {
            "data": async_redact_data(dict(entry.data), TO_REDACT),
            "options": async_redact_data(dict(entry.options), TO_REDACT),
        },
        "coordinator": {
            "last_update_success": coordinator.last_update_success,
            "update_interval_seconds": coordinator.update_interval.total_seconds()
            if coordinator.update_interval
            else None,
            "active_override": coordinator.active_override,
        },
    }

    # Add last optimization data (without raw_response to keep size down)
    if coordinator.data:
        data = dict(coordinator.data)
        data.pop("raw_response", None)
        diag["last_optimization"] = data
    else:
        diag["last_optimization"] = None

    # Add EOS server info
    try:
        health = await coordinator._eos_client.validate_server()
        diag["eos_server"] = {
            "reachable": True,
            "status": health.get("status"),
            "version": health.get("version"),
        }
    except Exception as err:
        diag["eos_server"] = {
            "reachable": False,
            "error": str(err),
        }

    return diag
