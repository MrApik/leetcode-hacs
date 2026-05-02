"""Tests for the calendar platform."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from aioresponses import aioresponses
from homeassistant.core import HomeAssistant
from pytest_homeassistant_custom_component.common import MockConfigEntry

from .const import TEST_USERNAME

pytestmark = pytest.mark.asyncio

CONTESTS = "calendar.leetcode_contests"
SUBMISSIONS = f"calendar.leetcode_{TEST_USERNAME}_submissions"


async def _setup(hass: HomeAssistant, config_entry: MockConfigEntry) -> None:
    config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()


async def test_contests_calendar_state(
    hass: HomeAssistant,
    stub_api: aioresponses,  # noqa: ARG001
    config_entry: MockConfigEntry,
) -> None:
    """The contests calendar surfaces the next upcoming contest."""
    await _setup(hass, config_entry)
    state = hass.states.get(CONTESTS)
    assert state is not None
    assert state.attributes.get("message") == "Weekly Contest 500"
    assert "leetcode.com/contest/weekly-contest-500" in state.attributes.get("location", "")


async def test_contests_calendar_get_events(
    hass: HomeAssistant,
    stub_api: aioresponses,  # noqa: ARG001
    config_entry: MockConfigEntry,
) -> None:
    """Querying the contests calendar returns all upcoming contests in window."""
    await _setup(hass, config_entry)
    start = datetime(2026, 1, 1, tzinfo=timezone.utc)
    end = datetime(2026, 12, 31, tzinfo=timezone.utc)
    events = await hass.services.async_call(
        "calendar",
        "get_events",
        {"entity_id": CONTESTS, "start_date_time": start, "end_date_time": end},
        blocking=True,
        return_response=True,
    )
    titles = [event["summary"] for event in events[CONTESTS]["events"]]
    assert "Weekly Contest 500" in titles
    assert "Biweekly Contest 182" in titles


async def test_submissions_calendar_state(
    hass: HomeAssistant,
    stub_api: aioresponses,  # noqa: ARG001
    config_entry: MockConfigEntry,
) -> None:
    """The submissions calendar surfaces today's activity if any."""
    await _setup(hass, config_entry)
    state = hass.states.get(SUBMISSIONS)
    assert state is not None
    # Today (2026-04-28) has 1 submission in the fixture calendar.
    assert "1 submission" in state.attributes.get("message", "")
