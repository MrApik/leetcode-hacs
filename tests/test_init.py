"""Tests for setup, unload, and runtime_data plumbing."""

from __future__ import annotations

import pytest
from aioresponses import aioresponses
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from pytest_homeassistant_custom_component.common import MockConfigEntry

pytestmark = pytest.mark.asyncio


async def test_setup_and_unload(
    hass: HomeAssistant,
    stub_api: aioresponses,  # noqa: ARG001 — provides background HTTP fixtures.
    config_entry: MockConfigEntry,
) -> None:
    """The integration sets up cleanly and unloads cleanly."""
    config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    assert config_entry.state is ConfigEntryState.LOADED
    assert config_entry.runtime_data is not None
    assert config_entry.runtime_data.coordinator.last_update_success is True

    assert await hass.config_entries.async_unload(config_entry.entry_id)
    await hass.async_block_till_done()
    assert config_entry.state is ConfigEntryState.NOT_LOADED


async def test_setup_retries_on_api_error(
    hass: HomeAssistant,
    mock_aioresponse: aioresponses,
    config_entry: MockConfigEntry,
) -> None:
    """Transport failure during first refresh marks the entry as `SETUP_RETRY`."""
    mock_aioresponse.get(
        f"{config_entry.data['base_url']}/{config_entry.data['username']}",
        status=500,
        repeat=True,
    )
    config_entry.add_to_hass(hass)
    assert not await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()
    assert config_entry.state is ConfigEntryState.SETUP_RETRY


async def test_setup_triggers_reauth_on_unknown_user(
    hass: HomeAssistant,
    mock_aioresponse: aioresponses,
    config_entry: MockConfigEntry,
) -> None:
    """A 404 during first refresh triggers the reauth flow."""
    mock_aioresponse.get(
        f"{config_entry.data['base_url']}/{config_entry.data['username']}",
        status=404,
        repeat=True,
    )
    config_entry.add_to_hass(hass)
    assert not await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()
    assert config_entry.state is ConfigEntryState.SETUP_ERROR

    flows = hass.config_entries.flow.async_progress_by_handler(config_entry.domain)
    assert any(flow["context"].get("source") == "reauth" for flow in flows)
