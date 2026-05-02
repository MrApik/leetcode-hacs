"""The LeetCode integration."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta
from typing import TYPE_CHECKING, Any, cast

import voluptuous as vol
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import SupportsResponse
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import LeetCodeApiClient, LeetCodeApiError
from .const import (
    CONF_BASE_URL,
    CONF_SCAN_INTERVAL,
    CONF_USERNAME,
    DEFAULT_BASE_URL,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
    SERVICE_FETCH_PROBLEM,
    SERVICE_REFRESH,
)
from .coordinator import LeetCodeDataUpdateCoordinator

if TYPE_CHECKING:
    from collections.abc import Callable, Coroutine

    from homeassistant.core import HomeAssistant, ServiceCall, ServiceResponse

PLATFORMS: list[Platform] = [
    Platform.BINARY_SENSOR,
    Platform.CALENDAR,
    Platform.SENSOR,
]

SERVICE_REFRESH_SCHEMA = vol.Schema({vol.Optional("entry_id"): cv.string})
SERVICE_FETCH_PROBLEM_SCHEMA = vol.Schema(
    {vol.Required("title_slug"): vol.All(cv.string, vol.Length(min=1))}
)


@dataclass(slots=True)
class LeetCodeRuntimeData:
    """Per-config-entry runtime objects, attached to `entry.runtime_data`."""

    coordinator: LeetCodeDataUpdateCoordinator
    client: LeetCodeApiClient


type LeetCodeConfigEntry = ConfigEntry[LeetCodeRuntimeData]


async def async_setup_entry(hass: HomeAssistant, entry: LeetCodeConfigEntry) -> bool:
    """Set up LeetCode from a config entry."""
    username: str = entry.data[CONF_USERNAME]
    base_url: str = entry.data.get(CONF_BASE_URL, DEFAULT_BASE_URL)
    interval_seconds: int | None = entry.options.get(CONF_SCAN_INTERVAL)
    update_interval = (
        timedelta(seconds=interval_seconds)
        if interval_seconds is not None
        else DEFAULT_SCAN_INTERVAL
    )

    session = async_get_clientsession(hass)
    client = LeetCodeApiClient(session, base_url=base_url, username=username)
    coordinator = LeetCodeDataUpdateCoordinator(
        hass, config_entry=entry, client=client, update_interval=update_interval
    )

    await coordinator.async_config_entry_first_refresh()

    entry.runtime_data = LeetCodeRuntimeData(coordinator=coordinator, client=client)
    entry.async_on_unload(entry.add_update_listener(_async_update_listener))

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    _async_register_services(hass)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: LeetCodeConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


async def _async_update_listener(hass: HomeAssistant, entry: LeetCodeConfigEntry) -> None:
    """Reload the integration when the user changes options."""
    await hass.config_entries.async_reload(entry.entry_id)


def _async_register_services(hass: HomeAssistant) -> None:
    """Register integration-wide services. Idempotent across config entries."""
    if not hass.services.has_service(DOMAIN, SERVICE_REFRESH):
        hass.services.async_register(
            DOMAIN,
            SERVICE_REFRESH,
            _make_refresh_handler(hass),
            schema=SERVICE_REFRESH_SCHEMA,
        )

    if not hass.services.has_service(DOMAIN, SERVICE_FETCH_PROBLEM):
        hass.services.async_register(
            DOMAIN,
            SERVICE_FETCH_PROBLEM,
            _make_fetch_problem_handler(hass),
            schema=SERVICE_FETCH_PROBLEM_SCHEMA,
            supports_response=SupportsResponse.ONLY,
        )


def _make_refresh_handler(
    hass: HomeAssistant,
) -> Callable[[ServiceCall], Coroutine[Any, Any, None]]:
    """Build the `refresh` service handler bound to `hass`."""

    async def _async_refresh(call: ServiceCall) -> None:
        entry_id = call.data.get("entry_id")
        if entry_id:
            entry = hass.config_entries.async_get_entry(entry_id)
            entries = [entry] if entry and entry.domain == DOMAIN else []
        else:
            entries = list(hass.config_entries.async_entries(DOMAIN))

        for entry in entries:
            data = getattr(entry, "runtime_data", None)
            if data is not None:
                await data.coordinator.async_request_refresh()

    return _async_refresh


def _make_fetch_problem_handler(
    hass: HomeAssistant,
) -> Callable[[ServiceCall], Coroutine[Any, Any, ServiceResponse]]:
    """Build the `fetch_problem` service handler bound to `hass`."""

    async def _async_fetch_problem(call: ServiceCall) -> ServiceResponse:
        entries = list(hass.config_entries.async_entries(DOMAIN))
        if not entries:
            raise ServiceValidationError(
                "No LeetCode profile is configured. Add one before calling fetch_problem."
            )
        # Any entry's client can fetch problem details — /select is not user-specific.
        for entry in entries:
            data = getattr(entry, "runtime_data", None)
            if data is not None:
                try:
                    problem = await data.client.async_fetch_problem(call.data["title_slug"])
                except LeetCodeApiError as err:
                    raise HomeAssistantError(str(err)) from err
                return cast("ServiceResponse", problem.to_dict())
        raise HomeAssistantError("No active LeetCode client available.")

    return _async_fetch_problem
