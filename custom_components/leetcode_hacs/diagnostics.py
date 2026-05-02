"""Diagnostics support for the LeetCode integration."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from homeassistant.components.diagnostics import async_redact_data

from .const import CONF_USERNAME

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant

    from . import LeetCodeConfigEntry

TO_REDACT: frozenset[str] = frozenset({CONF_USERNAME, "username", "userAvatar", "name"})


async def async_get_config_entry_diagnostics(
    _hass: HomeAssistant, entry: LeetCodeConfigEntry
) -> dict[str, Any]:
    """Return diagnostic data for the config entry, with PII redacted."""
    data = entry.runtime_data
    coordinator = data.coordinator
    return {
        "entry": {
            "title": entry.title,
            "data": async_redact_data(dict(entry.data), TO_REDACT),
            "options": dict(entry.options),
        },
        "coordinator": {
            "last_update_success": coordinator.last_update_success,
            "last_exception": repr(coordinator.last_exception)
            if coordinator.last_exception
            else None,
            "update_interval_seconds": coordinator.update_interval.total_seconds()
            if coordinator.update_interval
            else None,
        },
        "data": async_redact_data(coordinator.data.raw, TO_REDACT) if coordinator.data else None,
    }
