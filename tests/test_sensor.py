"""Tests for the sensor platform."""

from __future__ import annotations

import pytest
from aioresponses import aioresponses
from homeassistant.core import HomeAssistant
from pytest_homeassistant_custom_component.common import MockConfigEntry

from .const import TEST_USERNAME

pytestmark = pytest.mark.asyncio

HEADLINE = f"sensor.leetcode_{TEST_USERNAME}"
EASY = f"sensor.leetcode_{TEST_USERNAME}_easy_solved"
MEDIUM = f"sensor.leetcode_{TEST_USERNAME}_medium_solved"
HARD = f"sensor.leetcode_{TEST_USERNAME}_hard_solved"
CONTEST_RATING = f"sensor.leetcode_{TEST_USERNAME}_contest_rating"
RECENT = f"sensor.leetcode_{TEST_USERNAME}_recent_submissions"
TOP_LANG = f"sensor.leetcode_{TEST_USERNAME}_top_language"
TOP_SKILL = f"sensor.leetcode_{TEST_USERNAME}_top_skill"
DAILY = "sensor.leetcode_daily_challenge"


async def _setup(hass: HomeAssistant, config_entry: MockConfigEntry) -> None:
    config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()


@pytest.mark.parametrize(
    ("entity_id", "expected_state"),
    [
        (HEADLINE, "423"),
        (EASY, "215"),
        (MEDIUM, "178"),
        (HARD, "30"),
        (RECENT, "3"),
        (TOP_LANG, "Python3"),
        (TOP_SKILL, "Array"),
        (DAILY, "Two Sum"),
    ],
)
async def test_sensor_values(
    hass: HomeAssistant,
    stub_api: aioresponses,
    config_entry: MockConfigEntry,
    entity_id: str,
    expected_state: str,
) -> None:
    """Spot-check values for the most important entities."""
    await _setup(hass, config_entry)
    state = hass.states.get(entity_id)
    assert state is not None, f"missing entity {entity_id}"
    assert state.state == expected_state


async def test_headline_sensor_attributes(
    hass: HomeAssistant,
    stub_api: aioresponses,
    config_entry: MockConfigEntry,
) -> None:
    """The headline sensor exposes consolidated user metrics as attributes."""
    await _setup(hass, config_entry)
    state = hass.states.get(HEADLINE)
    assert state is not None
    attrs = state.attributes
    assert attrs["username"] == TEST_USERNAME
    assert attrs["profile_url"] == f"https://leetcode.com/{TEST_USERNAME}/"
    assert attrs["easy_solved"] == 215
    assert attrs["acceptance_rate"] == pytest.approx(67.3)
    assert attrs["global_ranking"] == 14523
    assert attrs["contest_rating"] == pytest.approx(1842.55)
    assert attrs["current_streak"] == 4
    assert attrs["last_submission"] is not None


async def test_recent_submissions_attributes(
    hass: HomeAssistant,
    stub_api: aioresponses,
    config_entry: MockConfigEntry,
) -> None:
    """`recent_submissions` exposes the full list of accepted submissions as attributes."""
    await _setup(hass, config_entry)
    state = hass.states.get(RECENT)
    assert state is not None
    submissions = state.attributes["submissions"]
    assert len(submissions) == 3
    first = submissions[0]
    assert first["title_slug"] == "two-sum"
    assert first["language"] == "python3"
    assert first["status"] == "Accepted"
    assert first["link"] == "https://leetcode.com/problems/two-sum/"


async def test_top_language_breakdown(
    hass: HomeAssistant,
    stub_api: aioresponses,
    config_entry: MockConfigEntry,
) -> None:
    """The top-language sensor exposes the per-language breakdown."""
    await _setup(hass, config_entry)
    state = hass.states.get(TOP_LANG)
    assert state is not None
    languages = state.attributes["languages"]
    names = [lang["name"] for lang in languages]
    assert "Python3" in names
    assert "C++" in names


async def test_top_skill_breakdown(
    hass: HomeAssistant,
    stub_api: aioresponses,
    config_entry: MockConfigEntry,
) -> None:
    """The top-skill sensor exposes the breakdown grouped by tier."""
    await _setup(hass, config_entry)
    state = hass.states.get(TOP_SKILL)
    assert state is not None
    assert state.attributes["tier"] == "fundamental"
    skills = state.attributes["skills"]
    by_tier = {entry["tier"] for entry in skills}
    assert by_tier == {"fundamental", "intermediate", "advanced"}


async def test_daily_challenge_sensor(
    hass: HomeAssistant,
    stub_api: aioresponses,
    config_entry: MockConfigEntry,
) -> None:
    """The daily challenge sensor exposes the full LeetCode metadata."""
    await _setup(hass, config_entry)
    state = hass.states.get(DAILY)
    assert state is not None
    attrs = state.attributes
    assert attrs["link"] == "https://leetcode.com/problems/two-sum/"
    assert attrs["question_id"] == "1"
    assert attrs["tags"] == ["Array", "Hash Table"]
    assert attrs["is_paid_only"] is False
