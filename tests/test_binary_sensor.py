"""Tests for the binary-sensor platform."""

from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import patch

import pytest
from aioresponses import aioresponses
from homeassistant.core import HomeAssistant
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.leetcode_hacs.const import CONF_STREAK_WARNING_HOUR

from .const import TEST_USERNAME

pytestmark = pytest.mark.asyncio

DAILY_SOLVED = f"binary_sensor.leetcode_{TEST_USERNAME}_daily_challenge_solved"
STREAK_AT_RISK = f"binary_sensor.leetcode_{TEST_USERNAME}_streak_at_risk"


async def _setup(hass: HomeAssistant, config_entry: MockConfigEntry) -> None:
    config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()


async def test_daily_solved_on(
    hass: HomeAssistant,
    stub_api: aioresponses,  # noqa: ARG001
    config_entry: MockConfigEntry,
) -> None:
    """The fixture has a submission for today's daily; the binary sensor is on."""
    await _setup(hass, config_entry)
    state = hass.states.get(DAILY_SOLVED)
    assert state is not None
    assert state.state == "on"
    assert state.attributes["link"] == "https://leetcode.com/problems/two-sum/"


async def test_streak_at_risk_off_when_solved_today(
    hass: HomeAssistant,
    stub_api: aioresponses,  # noqa: ARG001
    config_entry: MockConfigEntry,
) -> None:
    """If the user submitted today, streak-at-risk stays off regardless of hour."""
    await _setup(hass, config_entry)
    state = hass.states.get(STREAK_AT_RISK)
    assert state is not None
    assert state.state == "off"


async def test_streak_at_risk_on_when_late_and_no_submission(
    hass: HomeAssistant,
    mock_aioresponse: aioresponses,
    fixture_payloads: dict,
    config_entry: MockConfigEntry,
) -> None:
    """With no submission today AND past warning hour, streak-at-risk flips on."""
    yesterday_payload = {
        "count": 1,
        "submission": [
            {
                "title": "Add Two Numbers",
                "titleSlug": "add-two-numbers",
                "timestamp": "1777248000",  # 2026-04-27 UTC
                "statusDisplay": "Accepted",
                "lang": "python3",
            }
        ],
    }
    base = "https://api.example.test"
    user = TEST_USERNAME
    mock_aioresponse.get(f"{base}/{user}", payload=fixture_payloads["profile"])
    mock_aioresponse.get(f"{base}/{user}/contest", payload=fixture_payloads["contest"])
    mock_aioresponse.get(f"{base}/{user}/calendar", payload=fixture_payloads["calendar"])
    mock_aioresponse.get(
        f"{base}/{user}/acSubmission?limit=10", payload=yesterday_payload
    )
    mock_aioresponse.get(f"{base}/daily", payload=fixture_payloads["daily"])
    mock_aioresponse.get(f"{base}/{user}/language", payload=fixture_payloads["language"])
    mock_aioresponse.get(f"{base}/{user}/skill", payload=fixture_payloads["skill"])
    mock_aioresponse.get(
        f"{base}/contests/upcoming", payload=fixture_payloads["upcoming_contests"]
    )

    config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    coordinator = config_entry.runtime_data.coordinator

    # Pretend it is 21:00 local — past the default 20:00 warning hour.
    late_now = datetime(2026, 4, 28, 21, 0, tzinfo=timezone.utc)
    with patch(
        "custom_components.leetcode_hacs.binary_sensor.dt_util.now",
        return_value=late_now,
    ):
        # Force a state write so `is_on` is re-evaluated.
        await coordinator.async_refresh()
        await hass.async_block_till_done()
        state = hass.states.get(STREAK_AT_RISK)
        assert state is not None
        assert state.state == "on"


async def test_streak_at_risk_respects_options_warning_hour(
    hass: HomeAssistant,
    mock_aioresponse: aioresponses,
    fixture_payloads: dict,
    config_entry: MockConfigEntry,
) -> None:
    """A custom warning_hour option changes when the sensor flips on."""
    yesterday_payload = {
        "count": 1,
        "submission": [
            {
                "title": "Add Two Numbers",
                "titleSlug": "add-two-numbers",
                "timestamp": "1777248000",
                "statusDisplay": "Accepted",
                "lang": "python3",
            }
        ],
    }
    base = "https://api.example.test"
    user = TEST_USERNAME
    mock_aioresponse.get(f"{base}/{user}", payload=fixture_payloads["profile"], repeat=True)
    mock_aioresponse.get(
        f"{base}/{user}/contest", payload=fixture_payloads["contest"], repeat=True
    )
    mock_aioresponse.get(
        f"{base}/{user}/calendar", payload=fixture_payloads["calendar"], repeat=True
    )
    mock_aioresponse.get(
        f"{base}/{user}/acSubmission?limit=10", payload=yesterday_payload, repeat=True
    )
    mock_aioresponse.get(f"{base}/daily", payload=fixture_payloads["daily"], repeat=True)
    mock_aioresponse.get(
        f"{base}/{user}/language", payload=fixture_payloads["language"], repeat=True
    )
    mock_aioresponse.get(
        f"{base}/{user}/skill", payload=fixture_payloads["skill"], repeat=True
    )
    mock_aioresponse.get(
        f"{base}/contests/upcoming",
        payload=fixture_payloads["upcoming_contests"],
        repeat=True,
    )

    config_entry.add_to_hass(hass)
    hass.config_entries.async_update_entry(
        config_entry, options={CONF_STREAK_WARNING_HOUR: 6}
    )
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()
    coordinator = config_entry.runtime_data.coordinator

    morning = datetime(2026, 4, 28, 7, 0, tzinfo=timezone.utc)  # past warning_hour=6
    with patch(
        "custom_components.leetcode_hacs.binary_sensor.dt_util.now",
        return_value=morning,
    ):
        await coordinator.async_refresh()
        await hass.async_block_till_done()
        state = hass.states.get(STREAK_AT_RISK)
        assert state is not None
        assert state.state == "on"


async def test_streak_at_risk_off_when_streak_zero(
    hass: HomeAssistant,
    mock_aioresponse: aioresponses,
    fixture_payloads: dict,
    config_entry: MockConfigEntry,
) -> None:
    """If there's no streak to defend, streak-at-risk is always off."""
    base = "https://api.example.test"
    user = TEST_USERNAME
    mock_aioresponse.get(f"{base}/{user}", payload=fixture_payloads["profile"])
    mock_aioresponse.get(f"{base}/{user}/contest", payload=fixture_payloads["contest"])
    mock_aioresponse.get(
        f"{base}/{user}/calendar", payload={"submissionCalendar": {}}
    )
    mock_aioresponse.get(
        f"{base}/{user}/acSubmission?limit=10", payload={"count": 0, "submission": []}
    )
    mock_aioresponse.get(f"{base}/daily", payload=fixture_payloads["daily"])
    mock_aioresponse.get(f"{base}/{user}/language", payload=fixture_payloads["language"])
    mock_aioresponse.get(f"{base}/{user}/skill", payload=fixture_payloads["skill"])
    mock_aioresponse.get(
        f"{base}/contests/upcoming", payload=fixture_payloads["upcoming_contests"]
    )

    config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    state = hass.states.get(STREAK_AT_RISK)
    assert state is not None
    assert state.state == "off"
