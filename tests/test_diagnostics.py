"""Tests for the diagnostics module."""

from __future__ import annotations

import pytest
from aioresponses import aioresponses
from custom_components.leetcode_hacs.diagnostics import (
    async_get_config_entry_diagnostics,
)
from homeassistant.core import HomeAssistant
from pytest_homeassistant_custom_component.common import MockConfigEntry

pytestmark = pytest.mark.asyncio


async def test_diagnostics_redacts_username(
    hass: HomeAssistant,
    stub_api: aioresponses,
    config_entry: MockConfigEntry,
) -> None:
    """The username field in entry data is redacted."""
    config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    diagnostics = await async_get_config_entry_diagnostics(hass, config_entry)
    assert diagnostics["entry"]["data"]["username"] == "**REDACTED**"
    assert diagnostics["coordinator"]["last_update_success"] is True
    assert diagnostics["data"] is not None
