"""Tests for the integration's events."""

from __future__ import annotations

import dataclasses
from typing import Any
from unittest.mock import AsyncMock, patch

import pytest
from aioresponses import aioresponses
from homeassistant.core import HomeAssistant
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.leetcode_hacs.const import (
    EVENT_PROBLEM_SOLVED,
    EVENT_STREAK_MILESTONE,
)

pytestmark = pytest.mark.asyncio


async def _setup(hass: HomeAssistant, config_entry: MockConfigEntry) -> None:
    config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()


async def test_problem_solved_event_fires_on_increase(
    hass: HomeAssistant,
    stub_api: aioresponses,  # noqa: ARG001
    config_entry: MockConfigEntry,
) -> None:
    """When `total_solved` goes up between refreshes, the event fires once."""
    await _setup(hass, config_entry)
    coordinator = config_entry.runtime_data.coordinator
    initial = coordinator.data
    bumped = dataclasses.replace(initial, total_solved=initial.total_solved + 2)

    events: list[Any] = []
    hass.bus.async_listen(EVENT_PROBLEM_SOLVED, lambda e: events.append(e.data))

    with patch.object(
        coordinator.client, "async_fetch_stats", new=AsyncMock(return_value=bumped)
    ):
        await coordinator.async_refresh()
    await hass.async_block_till_done()

    assert len(events) == 1
    assert events[0]["previous_total"] == initial.total_solved
    assert events[0]["current_total"] == initial.total_solved + 2
    assert events[0]["delta"] == 2
    assert events[0]["newest_submission"] is not None


async def test_problem_solved_event_does_not_fire_on_first_refresh(
    hass: HomeAssistant,
    stub_api: aioresponses,  # noqa: ARG001
    config_entry: MockConfigEntry,
) -> None:
    """The first coordinator refresh sets baselines silently — no event."""
    events: list[Any] = []
    hass.bus.async_listen(EVENT_PROBLEM_SOLVED, lambda e: events.append(e.data))
    await _setup(hass, config_entry)
    assert events == []


async def test_streak_milestone_event_fires_when_crossing_threshold(
    hass: HomeAssistant,
    stub_api: aioresponses,  # noqa: ARG001
    config_entry: MockConfigEntry,
) -> None:
    """The streak_milestone event fires when crossing 7 / 30 / 100 / 365 days."""
    await _setup(hass, config_entry)
    coordinator = config_entry.runtime_data.coordinator
    initial = coordinator.data
    # Fixture streak is 4 — push to 7 to cross the first milestone.
    bumped = dataclasses.replace(initial, current_streak=7)

    events: list[Any] = []
    hass.bus.async_listen(EVENT_STREAK_MILESTONE, lambda e: events.append(e.data))

    with patch.object(
        coordinator.client, "async_fetch_stats", new=AsyncMock(return_value=bumped)
    ):
        await coordinator.async_refresh()
    await hass.async_block_till_done()

    assert len(events) == 1
    assert events[0]["milestone"] == 7
    assert events[0]["current_streak"] == 7


async def test_streak_milestone_event_fires_for_each_crossed_milestone(
    hass: HomeAssistant,
    stub_api: aioresponses,  # noqa: ARG001
    config_entry: MockConfigEntry,
) -> None:
    """Jumping from below-7 to above-30 fires both 7 and 30 events."""
    await _setup(hass, config_entry)
    coordinator = config_entry.runtime_data.coordinator
    initial = coordinator.data
    bumped = dataclasses.replace(initial, current_streak=35)

    events: list[Any] = []
    hass.bus.async_listen(EVENT_STREAK_MILESTONE, lambda e: events.append(e.data))

    with patch.object(
        coordinator.client, "async_fetch_stats", new=AsyncMock(return_value=bumped)
    ):
        await coordinator.async_refresh()
    await hass.async_block_till_done()

    milestones = sorted(event["milestone"] for event in events)
    assert milestones == [7, 30]
