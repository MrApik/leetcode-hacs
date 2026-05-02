"""Shared pytest fixtures."""

from __future__ import annotations

import json
from collections.abc import Generator
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest
from aioresponses import aioresponses
from custom_components.leetcode_hacs.const import (
    CONF_BASE_URL,
    CONF_USERNAME,
    DOMAIN,
)
from pytest_homeassistant_custom_component.common import MockConfigEntry

from .const import TEST_BASE_URL, TEST_USERNAME

FIXTURE_DIR = Path(__file__).parent / "fixtures"


def _load(fixture: str) -> dict[str, Any]:
    return json.loads((FIXTURE_DIR / fixture).read_text())


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations: None) -> None:
    """Auto-enable HA's custom-integration loader for every test."""


@pytest.fixture
def mock_aioresponse() -> Generator[aioresponses]:
    """Patch aiohttp transport with deterministic responses."""
    with aioresponses() as mocked:
        yield mocked


@pytest.fixture
def fixture_payloads() -> dict[str, dict[str, Any]]:
    """Return all canned API payloads keyed by endpoint slug."""
    return {
        "profile": _load("profile.json"),
        "contest": _load("contest.json"),
        "calendar": _load("calendar.json"),
        "ac_submission": _load("ac_submission.json"),
        "daily": _load("daily.json"),
        "language": _load("language.json"),
        "skill": _load("skill.json"),
        "upcoming_contests": _load("upcoming_contests.json"),
        "problem_select": _load("problem_select.json"),
    }


@pytest.fixture
def stub_api(
    mock_aioresponse: aioresponses, fixture_payloads: dict[str, dict[str, Any]]
) -> aioresponses:
    """Wire all API endpoints to canned responses for the happy path."""
    mock_aioresponse.get(
        f"{TEST_BASE_URL}/{TEST_USERNAME}/profile",
        payload=fixture_payloads["profile"],
        repeat=True,
    )
    mock_aioresponse.get(
        f"{TEST_BASE_URL}/{TEST_USERNAME}/contest",
        payload=fixture_payloads["contest"],
        repeat=True,
    )
    mock_aioresponse.get(
        f"{TEST_BASE_URL}/{TEST_USERNAME}/calendar",
        payload=fixture_payloads["calendar"],
        repeat=True,
    )
    mock_aioresponse.get(
        f"{TEST_BASE_URL}/{TEST_USERNAME}/acSubmission?limit=10",
        payload=fixture_payloads["ac_submission"],
        repeat=True,
    )
    mock_aioresponse.get(
        f"{TEST_BASE_URL}/daily",
        payload=fixture_payloads["daily"],
        repeat=True,
    )
    mock_aioresponse.get(
        f"{TEST_BASE_URL}/{TEST_USERNAME}/language",
        payload=fixture_payloads["language"],
        repeat=True,
    )
    mock_aioresponse.get(
        f"{TEST_BASE_URL}/{TEST_USERNAME}/skill",
        payload=fixture_payloads["skill"],
        repeat=True,
    )
    mock_aioresponse.get(
        f"{TEST_BASE_URL}/contests/upcoming",
        payload=fixture_payloads["upcoming_contests"],
        repeat=True,
    )
    mock_aioresponse.get(
        f"{TEST_BASE_URL}/select?titleSlug=two-sum",
        payload=fixture_payloads["problem_select"],
        repeat=True,
    )
    return mock_aioresponse


@pytest.fixture
def config_entry() -> MockConfigEntry:
    """Build a `MockConfigEntry` matching the canned fixture data."""
    return MockConfigEntry(
        domain=DOMAIN,
        title=TEST_USERNAME,
        data={CONF_USERNAME: TEST_USERNAME, CONF_BASE_URL: TEST_BASE_URL},
        unique_id=f"api.example.test::{TEST_USERNAME.lower()}",
    )


@pytest.fixture(autouse=True)
def freeze_today(monkeypatch: pytest.MonkeyPatch) -> datetime:
    """Pin "now" everywhere the integration reads it, so logic is deterministic.

    Patches both `api.datetime.now` (used by the upstream-payload parsers) and
    `binary_sensor.dt_util.now` (used by the streak-at-risk gate) to a fixed
    moment in UTC. Individual tests may further patch the latter to simulate
    "later in the day".
    """
    fixed = datetime(2026, 4, 28, 12, 0, tzinfo=UTC)

    class _FixedDatetime(datetime):
        @classmethod
        def now(cls, tz: Any = None) -> datetime:  # type: ignore[override]
            return fixed if tz is None else fixed.astimezone(tz)

    monkeypatch.setattr("custom_components.leetcode_hacs.api.datetime", _FixedDatetime)
    monkeypatch.setattr("custom_components.leetcode_hacs.binary_sensor.dt_util.now", lambda: fixed)
    return fixed
