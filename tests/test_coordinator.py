"""Direct tests for the API client and coordinator behaviour."""

from __future__ import annotations

import json
from datetime import UTC, date, datetime

import pytest
from aiohttp import ClientSession
from aioresponses import aioresponses
from custom_components.leetcode_hacs.api import (
    DailyChallenge,
    LeetCodeApiClient,
    LeetCodeAuthError,
    LeetCodeRateLimitError,
    RecentSubmission,
    _calculate_streak,
    _parse_submission_calendar,
    _solved_today,
)

from .const import TEST_BASE_URL, TEST_USERNAME


def _daily(slug: str = "two-sum") -> DailyChallenge:
    return DailyChallenge(
        date="2026-04-28",
        title="Two Sum",
        title_slug=slug,
        difficulty="easy",
        link=f"https://leetcode.com/problems/{slug}/",
        question_id="1",
        tags=("Array",),
        is_paid_only=False,
    )


def _submission(slug: str, ts: int, *, lang: str = "python3") -> RecentSubmission:
    return RecentSubmission(
        title=slug.replace("-", " ").title(),
        title_slug=slug,
        timestamp=datetime.fromtimestamp(ts, tz=UTC),
        language=lang,
        status="Accepted",
    )


@pytest.mark.asyncio
async def test_fetch_stats_round_trip(stub_api: aioresponses) -> None:
    """`async_fetch_stats` aggregates all endpoints into a `UserStats`."""
    async with ClientSession() as session:
        client = LeetCodeApiClient(session, base_url=TEST_BASE_URL, username=TEST_USERNAME)
        stats = await client.async_fetch_stats()

    assert stats.username == TEST_USERNAME
    assert stats.total_solved == 423
    assert stats.contest_rating == pytest.approx(1842.55)
    assert stats.current_streak == 4
    assert stats.daily_challenge.title == "Two Sum"
    assert stats.daily_solved is True
    assert len(stats.recent_submissions) == 3
    assert stats.recent_submissions[0].title_slug == "two-sum"
    assert stats.top_language is not None
    assert stats.top_language.name == "Python3"
    assert stats.top_skill is not None
    assert stats.top_skill.name == "Array"
    assert len(stats.upcoming_contests) == 2
    # Sorted ascending by start time.
    assert stats.upcoming_contests[0].start_time < stats.upcoming_contests[1].start_time


@pytest.mark.asyncio
async def test_fetch_stats_tolerates_aux_endpoint_failures(
    mock_aioresponse: aioresponses, fixture_payloads: dict
) -> None:
    """A failing /skill endpoint must not break the whole refresh."""
    mock_aioresponse.get(
        f"{TEST_BASE_URL}/{TEST_USERNAME}/profile", payload=fixture_payloads["profile"]
    )
    mock_aioresponse.get(
        f"{TEST_BASE_URL}/{TEST_USERNAME}/contest", payload=fixture_payloads["contest"]
    )
    mock_aioresponse.get(
        f"{TEST_BASE_URL}/{TEST_USERNAME}/calendar", payload=fixture_payloads["calendar"]
    )
    mock_aioresponse.get(
        f"{TEST_BASE_URL}/{TEST_USERNAME}/acSubmission?limit=10",
        payload=fixture_payloads["ac_submission"],
    )
    mock_aioresponse.get(f"{TEST_BASE_URL}/daily", payload=fixture_payloads["daily"])
    mock_aioresponse.get(f"{TEST_BASE_URL}/{TEST_USERNAME}/language", status=500)
    mock_aioresponse.get(f"{TEST_BASE_URL}/{TEST_USERNAME}/skill", status=500)
    mock_aioresponse.get(f"{TEST_BASE_URL}/contests/upcoming", status=500)

    async with ClientSession() as session:
        client = LeetCodeApiClient(session, base_url=TEST_BASE_URL, username=TEST_USERNAME)
        stats = await client.async_fetch_stats()

    assert stats.languages == ()
    assert stats.skills == ()
    assert stats.upcoming_contests == ()
    # Core data still present.
    assert stats.total_solved == 423


@pytest.mark.asyncio
async def test_validate_404_raises_auth_error(mock_aioresponse: aioresponses) -> None:
    """A 404 from the username endpoint raises `LeetCodeAuthError`."""
    mock_aioresponse.get(f"{TEST_BASE_URL}/{TEST_USERNAME}/profile", status=404)
    async with ClientSession() as session:
        client = LeetCodeApiClient(session, base_url=TEST_BASE_URL, username=TEST_USERNAME)
        with pytest.raises(LeetCodeAuthError):
            await client.async_validate()


@pytest.mark.asyncio
async def test_validate_429_raises_rate_limit(mock_aioresponse: aioresponses) -> None:
    """A 429 raises `LeetCodeRateLimitError`."""
    mock_aioresponse.get(f"{TEST_BASE_URL}/{TEST_USERNAME}/profile", status=429)
    async with ClientSession() as session:
        client = LeetCodeApiClient(session, base_url=TEST_BASE_URL, username=TEST_USERNAME)
        with pytest.raises(LeetCodeRateLimitError):
            await client.async_validate()


@pytest.mark.asyncio
async def test_async_fetch_problem(stub_api: aioresponses) -> None:
    """`async_fetch_problem` parses /select responses correctly."""
    async with ClientSession() as session:
        client = LeetCodeApiClient(session, base_url=TEST_BASE_URL, username=TEST_USERNAME)
        problem = await client.async_fetch_problem("two-sum")
    assert problem.title == "Two Sum"
    assert problem.question_id == "1"
    assert problem.tags == ("Array", "Hash Table")
    assert len(problem.hints) == 2
    assert problem.likes == 60000


def test_parse_submission_calendar_handles_dict(freeze_today: datetime) -> None:
    """A dict payload is accepted and zero-count days are dropped."""
    today_ts = int(freeze_today.replace(hour=0, minute=0, second=0).timestamp())
    raw = {str(today_ts): 3, str(today_ts - 86400): 1, str(today_ts - 2 * 86400): 0}
    parsed = _parse_submission_calendar(raw)
    assert len(parsed) == 2
    # Sorted ascending.
    assert parsed[0][0] < parsed[1][0]


def test_parse_submission_calendar_handles_string(freeze_today: datetime) -> None:
    """A JSON-encoded string payload is also accepted."""
    today_ts = int(freeze_today.replace(hour=0, minute=0, second=0).timestamp())
    payload = json.dumps({str(today_ts): 1, str(today_ts - 86400): 1})
    parsed = _parse_submission_calendar(payload)
    assert len(parsed) == 2


def test_parse_submission_calendar_invalid_inputs() -> None:
    """Garbage inputs return an empty tuple instead of crashing."""
    assert _parse_submission_calendar(None) == ()
    assert _parse_submission_calendar("not json") == ()
    assert _parse_submission_calendar(123) == ()


def test_calculate_streak_today_and_yesterday(freeze_today: datetime) -> None:
    """Counts consecutive days ending today."""
    today = freeze_today.date()
    yesterday = date.fromordinal(today.toordinal() - 1)
    cal = ((yesterday, 5), (today, 3))
    assert _calculate_streak(cal) == 2


def test_calculate_streak_grace_period(freeze_today: datetime) -> None:
    """If the user hasn't submitted today yet, yesterday's streak still counts."""
    today = freeze_today.date()
    yesterday = date.fromordinal(today.toordinal() - 1)
    day_before = date.fromordinal(today.toordinal() - 2)
    cal = ((day_before, 5), (yesterday, 5))
    assert _calculate_streak(cal) == 2


def test_calculate_streak_empty() -> None:
    """An empty calendar yields zero."""
    assert _calculate_streak(()) == 0


def test_solved_today_no_match(freeze_today: datetime) -> None:
    """A submission for a different problem on a different slug does not count."""
    daily = _daily(slug="some-other-problem")
    submissions = (_submission("two-sum", 1777334400),)
    assert _solved_today(submissions, daily) is False


def test_solved_today_match(freeze_today: datetime) -> None:
    """A submission for today's daily on today's date counts as solved."""
    daily = _daily(slug="two-sum")
    submissions = (_submission("two-sum", 1777334400),)
    assert _solved_today(submissions, daily) is True


def test_solved_today_wrong_day(freeze_today: datetime) -> None:
    """A matching slug submitted on a different day does NOT count as solved."""
    daily = _daily(slug="two-sum")
    yesterday_ts = 1777248000
    submissions = (_submission("two-sum", yesterday_ts),)
    assert _solved_today(submissions, daily) is False


def test_daily_challenge_from_flat_payload() -> None:
    """The parser handles the real (flat) `/daily` shape with topic tags."""
    payload = {
        "questionLink": "https://leetcode.com/problems/two-sum/",
        "date": "2026-04-28",
        "questionFrontendId": "1",
        "questionTitle": "Two Sum",
        "titleSlug": "two-sum",
        "difficulty": "Easy",
        "isPaidOnly": False,
        "topicTags": [
            {"name": "Array", "slug": "array", "translatedName": None},
            {"name": "Hash Table", "slug": "hash-table", "translatedName": None},
        ],
    }
    daily = DailyChallenge.from_payload(payload)
    assert daily.title == "Two Sum"
    assert daily.tags == ("Array", "Hash Table")
    assert daily.is_paid_only is False
    assert daily.link == "https://leetcode.com/problems/two-sum/"
