"""Async client for the alfa-leetcode-api community service."""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from datetime import UTC, date, datetime, timedelta
from http import HTTPStatus
from typing import Any, Self

from aiohttp import ClientError, ClientResponseError, ClientSession, ClientTimeout
from yarl import URL

from .const import REQUEST_TIMEOUT

_LOGGER = logging.getLogger(__name__)

RECENT_SUBMISSION_LIMIT = 10


class LeetCodeApiError(Exception):
    """Raised when the upstream API returns an unrecoverable error."""


class LeetCodeAuthError(LeetCodeApiError):
    """Raised when the configured username is rejected by the API."""


class LeetCodeRateLimitError(LeetCodeApiError):
    """Raised when the upstream rate limit (120/hour/IP by default) is hit."""


@dataclass(slots=True, frozen=True)
class DailyChallenge:
    """Today's daily LeetCode challenge."""

    date: str
    title: str
    title_slug: str
    difficulty: str
    link: str
    question_id: str
    tags: tuple[str, ...]
    is_paid_only: bool

    @classmethod
    def from_payload(cls, payload: dict[str, Any]) -> Self:
        """Build a `DailyChallenge` from the `/daily` API response.

        The upstream response is flat — `questionTitle`, `titleSlug`,
        `questionFrontendId`, `topicTags`, etc. are top-level keys. The
        nested `question` field is the HTML problem description (a string,
        not an object), so it is intentionally ignored here.
        """
        title_slug = str(payload.get("titleSlug", ""))
        link = str(payload.get("questionLink") or "")
        if not link and title_slug:
            link = f"https://leetcode.com/problems/{title_slug}/"

        raw_tags = payload.get("topicTags") or []
        tags = tuple(str(t["name"]) for t in raw_tags if isinstance(t, dict) and t.get("name"))

        return cls(
            date=str(payload.get("date", "")),
            title=str(payload.get("questionTitle", "")),
            title_slug=title_slug,
            difficulty=str(payload.get("difficulty", "")).lower(),
            link=link,
            question_id=str(payload.get("questionFrontendId", "")),
            tags=tags,
            is_paid_only=bool(payload.get("isPaidOnly", False)),
        )


@dataclass(slots=True, frozen=True)
class RecentSubmission:
    """A single accepted submission from the user's history."""

    title: str
    title_slug: str
    timestamp: datetime
    language: str
    status: str

    @property
    def link(self) -> str:
        """Return the canonical URL of the submitted problem."""
        return f"https://leetcode.com/problems/{self.title_slug}/"


@dataclass(slots=True, frozen=True)
class LanguageStat:
    """A single programming-language entry in the user's language stats."""

    name: str
    problems_solved: int


@dataclass(slots=True, frozen=True)
class SkillStat:
    """A single topic-tag entry in the user's skill stats."""

    name: str
    slug: str
    problems_solved: int
    tier: str  # "fundamental" | "intermediate" | "advanced"


@dataclass(slots=True, frozen=True)
class ContestEvent:
    """An upcoming LeetCode contest."""

    title: str
    title_slug: str
    start_time: datetime
    duration_seconds: int
    is_virtual: bool
    contains_premium: bool

    @property
    def end_time(self) -> datetime:
        """The contest's scheduled end time."""
        return self.start_time + timedelta(seconds=self.duration_seconds)

    @property
    def link(self) -> str:
        """The contest page on leetcode.com."""
        return f"https://leetcode.com/contest/{self.title_slug}/"


@dataclass(slots=True, frozen=True)
class ProblemDetail:
    """The metadata returned by `/select?titleSlug=...` for a single problem."""

    title: str
    title_slug: str
    question_id: str
    difficulty: str
    is_paid_only: bool
    link: str
    tags: tuple[str, ...]
    hints: tuple[str, ...]
    likes: int
    dislikes: int

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-serialisable representation for service responses."""
        return {
            "title": self.title,
            "title_slug": self.title_slug,
            "question_id": self.question_id,
            "difficulty": self.difficulty,
            "is_paid_only": self.is_paid_only,
            "link": self.link,
            "tags": list(self.tags),
            "hints": list(self.hints),
            "likes": self.likes,
            "dislikes": self.dislikes,
        }


@dataclass(slots=True, frozen=True)
class UserStats:
    """Aggregate user statistics returned by the integration's coordinator."""

    username: str
    total_solved: int
    easy_solved: int
    medium_solved: int
    hard_solved: int
    total_questions: int
    acceptance_rate: float | None
    ranking: int | None
    contest_rating: float | None
    contest_global_ranking: int | None
    contests_attended: int | None
    top_percentage: float | None
    current_streak: int
    last_submission: datetime | None
    daily_challenge: DailyChallenge
    daily_solved: bool
    recent_submissions: tuple[RecentSubmission, ...]
    languages: tuple[LanguageStat, ...]
    skills: tuple[SkillStat, ...]
    submission_calendar: tuple[tuple[date, int], ...]
    upcoming_contests: tuple[ContestEvent, ...]
    raw: dict[str, Any] = field(repr=False, compare=False)

    @property
    def top_language(self) -> LanguageStat | None:
        """Return the language with the most problems solved (or `None`)."""
        if not self.languages:
            return None
        return max(self.languages, key=lambda lang: lang.problems_solved)

    @property
    def top_skill(self) -> SkillStat | None:
        """Return the topic tag with the most problems solved (or `None`)."""
        if not self.skills:
            return None
        return max(self.skills, key=lambda skill: skill.problems_solved)


class LeetCodeApiClient:
    """Thin async wrapper around the alfa-leetcode-api endpoints we consume."""

    def __init__(self, session: ClientSession, base_url: str, username: str) -> None:
        """Create a client bound to a single LeetCode username."""
        self._session = session
        self._base_url = URL(base_url.rstrip("/"))
        self._username = username

    @property
    def username(self) -> str:
        """The username this client queries."""
        return self._username

    @property
    def base_url(self) -> str:
        """The base URL this client queries."""
        return str(self._base_url)

    async def async_validate(self) -> None:
        """Verify that the configured username exists on the upstream service."""
        await self._get(f"/{self._username}/profile")

    async def async_fetch_stats(self) -> UserStats:
        """Fetch and assemble all data needed to populate the integration's entities."""
        profile = await self._get(f"/{self._username}/profile")
        contest = await self._get(f"/{self._username}/contest")
        calendar = await self._get(f"/{self._username}/calendar")
        ac_submission = await self._get(
            f"/{self._username}/acSubmission", limit=RECENT_SUBMISSION_LIMIT
        )
        daily = await self._get("/daily")
        # Auxiliary endpoints — failures degrade gracefully so a transient
        # GraphQL error on /skill does not break the whole refresh.
        language = await self._try_get(f"/{self._username}/language") or {}
        skill = await self._try_get(f"/{self._username}/skill") or {}
        contests_payload = await self._try_get("/contests/upcoming") or {}

        daily_challenge = DailyChallenge.from_payload(daily)
        recent = _extract_recent_submissions(ac_submission)
        last_submission = recent[0].timestamp if recent else None
        submission_calendar = _parse_submission_calendar(calendar.get("submissionCalendar"))
        streak = _calculate_streak(submission_calendar)
        daily_solved = _solved_today(recent, daily_challenge)
        languages = _extract_languages(language)
        skills = _extract_skills(skill)
        upcoming_contests = _extract_contests(contests_payload)

        return UserStats(
            username=self._username,
            total_solved=int(profile.get("totalSolved", 0) or 0),
            easy_solved=int(profile.get("easySolved", 0) or 0),
            medium_solved=int(profile.get("mediumSolved", 0) or 0),
            hard_solved=int(profile.get("hardSolved", 0) or 0),
            total_questions=int(profile.get("totalQuestions", 0) or 0),
            acceptance_rate=_compute_acceptance_rate(profile),
            ranking=_optional_int(profile.get("ranking")),
            contest_rating=_optional_float(contest.get("contestRating")),
            contest_global_ranking=_optional_int(contest.get("contestGlobalRanking")),
            contests_attended=_optional_int(contest.get("contestAttend")),
            top_percentage=_optional_float(contest.get("contestTopPercentage")),
            current_streak=streak,
            last_submission=last_submission,
            daily_challenge=daily_challenge,
            daily_solved=daily_solved,
            recent_submissions=recent,
            languages=languages,
            skills=skills,
            submission_calendar=submission_calendar,
            upcoming_contests=upcoming_contests,
            raw={
                "profile": profile,
                "contest": contest,
                "calendar": calendar,
                "ac_submission": ac_submission,
                "daily": daily,
                "language": language,
                "skill": skill,
                "contests": contests_payload,
            },
        )

    async def async_fetch_problem(self, title_slug: str) -> ProblemDetail:
        """Fetch a single problem's metadata by its title slug."""
        payload = await self._get("/select", titleSlug=title_slug)
        title_slug_resp = str(payload.get("titleSlug", title_slug))
        link = str(payload.get("link") or payload.get("questionLink") or "")
        if not link:
            link = f"https://leetcode.com/problems/{title_slug_resp}/"
        raw_tags = payload.get("topicTags") or []
        tags = tuple(str(t["name"]) for t in raw_tags if isinstance(t, dict) and t.get("name"))
        raw_hints = payload.get("hints") or []
        hints = tuple(str(h) for h in raw_hints if h)
        return ProblemDetail(
            title=str(payload.get("questionTitle", "")),
            title_slug=title_slug_resp,
            question_id=str(payload.get("questionFrontendId", "")),
            difficulty=str(payload.get("difficulty", "")).lower(),
            is_paid_only=bool(payload.get("isPaidOnly", False)),
            link=link,
            tags=tags,
            hints=hints,
            likes=int(payload.get("likes", 0) or 0),
            dislikes=int(payload.get("dislikes", 0) or 0),
        )

    async def _try_get(self, path: str, **params: Any) -> dict[str, Any] | None:
        """Best-effort `_get` — returns `None` instead of raising."""
        try:
            return await self._get(path, **params)
        except (LeetCodeApiError, LeetCodeAuthError) as err:
            _LOGGER.debug("Optional endpoint %s failed: %s", path, err)
            return None

    async def _get(self, path: str, **params: Any) -> dict[str, Any]:
        # Strip trailing `/` from the base path and ensure the suffix starts with one,
        # so a host-only base URL (whose `.path` is `/`) does not produce `//foo`.
        base_path = self._base_url.path.rstrip("/")
        suffix = path if path.startswith("/") else f"/{path}"
        url = self._base_url.with_path(f"{base_path}{suffix}")
        try:
            async with self._session.get(
                url, params=params or None, timeout=ClientTimeout(total=REQUEST_TIMEOUT)
            ) as response:
                if response.status == HTTPStatus.NOT_FOUND:
                    raise LeetCodeAuthError(f"User '{self._username}' not found")
                if response.status == HTTPStatus.TOO_MANY_REQUESTS:
                    raise LeetCodeRateLimitError(
                        "Upstream API rate limit exceeded (120/hour/IP). "
                        "Consider self-hosting alfa-leetcode-api."
                    )
                response.raise_for_status()
                payload = await response.json(content_type=None)
        except LeetCodeApiError:
            raise
        except ClientResponseError as err:
            raise LeetCodeApiError(f"Upstream returned HTTP {err.status}") from err
        except (ClientError, TimeoutError) as err:
            raise LeetCodeApiError(f"Network error contacting {url}") from err

        if isinstance(payload, dict) and (
            payload.get("errors")
            or payload.get("error")
            or payload.get("message") == "User not found"
        ):
            message = payload.get("error") or payload.get("message") or payload.get("errors")
            raise LeetCodeAuthError(str(message))
        if not isinstance(payload, dict):
            raise LeetCodeApiError(
                f"Unexpected response shape from {path}: {type(payload).__name__}"
            )
        return payload


def _optional_int(value: Any) -> int | None:
    if value in (None, "", "N/A"):
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _optional_float(value: Any) -> float | None:
    if value in (None, "", "N/A"):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _compute_acceptance_rate(profile: dict[str, Any]) -> float | None:
    """Derive acceptance rate from `matchedUserStats` (`/profile` doesn't expose it directly)."""
    stats = profile.get("matchedUserStats") or {}
    ac = stats.get("acSubmissionNum") or []
    total = stats.get("totalSubmissionNum") or []
    ac_all = next((entry for entry in ac if entry.get("difficulty") == "All"), None)
    total_all = next(
        (entry for entry in total if entry.get("difficulty") == "All"), None
    )
    if not ac_all or not total_all:
        return None
    try:
        ac_count = int(ac_all.get("submissions", 0))
        total_count = int(total_all.get("submissions", 0))
    except (TypeError, ValueError):
        return None
    if total_count <= 0:
        return None
    return round(ac_count / total_count * 100, 2)


def _parse_submission_calendar(raw: Any) -> tuple[tuple[date, int], ...]:
    """Normalise the calendar payload (string or dict) into sorted (date, count) tuples."""
    if not raw:
        return ()
    if isinstance(raw, str):
        try:
            raw = json.loads(raw)
        except json.JSONDecodeError:
            return ()
    if not isinstance(raw, dict):
        return ()
    parsed: list[tuple[date, int]] = []
    for ts, count in raw.items():
        try:
            seconds = int(ts)
            count_int = int(count)
        except (TypeError, ValueError):
            continue
        if count_int <= 0:
            continue
        day = datetime.fromtimestamp(seconds, tz=UTC).date()
        parsed.append((day, count_int))
    parsed.sort(key=lambda item: item[0])
    return tuple(parsed)


def _calculate_streak(calendar: tuple[tuple[date, int], ...]) -> int:
    """Return the number of consecutive days (ending today UTC) with submissions."""
    if not calendar:
        return 0
    days = {day for day, _ in calendar}
    today = datetime.now(tz=UTC).date()
    streak = 0
    cursor = today
    while cursor in days:
        streak += 1
        cursor = date.fromordinal(cursor.toordinal() - 1)
    if streak == 0:
        # Allow a one-day grace if the user has not yet submitted today.
        cursor = date.fromordinal(today.toordinal() - 1)
        while cursor in days:
            streak += 1
            cursor = date.fromordinal(cursor.toordinal() - 1)
    return streak


def _extract_recent_submissions(payload: dict[str, Any]) -> tuple[RecentSubmission, ...]:
    """Convert the `/<user>/acSubmission` payload into typed records, newest-first."""
    submissions = payload.get("submission") or []
    out: list[RecentSubmission] = []
    for entry in submissions:
        if not isinstance(entry, dict):
            continue
        ts_raw = entry.get("timestamp")
        if ts_raw is None:
            continue
        try:
            seconds = int(ts_raw)
        except (TypeError, ValueError):
            continue
        out.append(
            RecentSubmission(
                title=str(entry.get("title", "")),
                title_slug=str(entry.get("titleSlug", "")),
                timestamp=datetime.fromtimestamp(seconds, tz=UTC),
                language=str(entry.get("lang", "")),
                status=str(entry.get("statusDisplay", "")),
            )
        )
    return tuple(out)


def _solved_today(submissions: tuple[RecentSubmission, ...], daily: DailyChallenge) -> bool:
    """Return whether any of `submissions` matches today's daily challenge slug (UTC)."""
    if not daily.title_slug:
        return False
    today = datetime.now(tz=UTC).date()
    return any(
        s.title_slug == daily.title_slug and s.timestamp.date() == today for s in submissions
    )


def _extract_languages(payload: dict[str, Any]) -> tuple[LanguageStat, ...]:
    raw = payload.get("languageProblemCount") or []
    out: list[LanguageStat] = []
    for entry in raw:
        if not isinstance(entry, dict):
            continue
        name = str(entry.get("languageName", ""))
        if not name:
            continue
        try:
            count = int(entry.get("problemsSolved", 0))
        except (TypeError, ValueError):
            count = 0
        out.append(LanguageStat(name=name, problems_solved=count))
    return tuple(out)


def _extract_skills(payload: dict[str, Any]) -> tuple[SkillStat, ...]:
    out: list[SkillStat] = []
    for tier in ("fundamental", "intermediate", "advanced"):
        for entry in payload.get(tier) or []:
            if not isinstance(entry, dict):
                continue
            name = str(entry.get("tagName", ""))
            slug = str(entry.get("tagSlug", ""))
            if not name:
                continue
            try:
                count = int(entry.get("problemsSolved", 0))
            except (TypeError, ValueError):
                count = 0
            out.append(SkillStat(name=name, slug=slug, problems_solved=count, tier=tier))
    return tuple(out)


def _extract_contests(payload: dict[str, Any]) -> tuple[ContestEvent, ...]:
    raw = payload.get("contests") or []
    out: list[ContestEvent] = []
    for entry in raw:
        if not isinstance(entry, dict):
            continue
        start_raw = entry.get("startTime")
        duration_raw = entry.get("duration")
        if start_raw is None or duration_raw is None:
            continue
        try:
            start = int(start_raw)
            duration = int(duration_raw)
        except (TypeError, ValueError):
            continue
        out.append(
            ContestEvent(
                title=str(entry.get("title", "")),
                title_slug=str(entry.get("titleSlug", "")),
                start_time=datetime.fromtimestamp(start, tz=UTC),
                duration_seconds=duration,
                is_virtual=bool(entry.get("isVirtual", False)),
                contains_premium=bool(entry.get("containsPremium", False)),
            )
        )
    out.sort(key=lambda c: c.start_time)
    return tuple(out)
