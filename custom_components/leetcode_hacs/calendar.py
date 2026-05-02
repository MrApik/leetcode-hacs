"""Calendar platform for the LeetCode integration."""

from __future__ import annotations

from datetime import UTC, date, datetime, time, timedelta
from typing import TYPE_CHECKING

from homeassistant.components.calendar import (
    CalendarEntity,
    CalendarEntityDescription,
    CalendarEvent,
)

from .api import ContestEvent
from .entity import LeetCodeGlobalEntity, LeetCodeUserEntity

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant
    from homeassistant.helpers.entity_platform import AddEntitiesCallback

    from . import LeetCodeConfigEntry
    from .coordinator import LeetCodeDataUpdateCoordinator

PARALLEL_UPDATES = 0

CONTESTS_DESCRIPTION = CalendarEntityDescription(
    key="contests",
    translation_key="contests",
    icon="mdi:trophy-outline",
)

SUBMISSIONS_DESCRIPTION = CalendarEntityDescription(
    key="submissions",
    translation_key="submissions",
    icon="mdi:calendar-check",
)


async def async_setup_entry(
    _hass: HomeAssistant,
    entry: LeetCodeConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the calendar platform from a config entry."""
    coordinator = entry.runtime_data.coordinator
    async_add_entities(
        [
            LeetCodeContestsCalendar(coordinator),
            LeetCodeSubmissionsCalendar(coordinator),
        ]
    )


class LeetCodeContestsCalendar(LeetCodeGlobalEntity, CalendarEntity):
    """Calendar of upcoming LeetCode contests (Weekly, Biweekly)."""

    entity_description: CalendarEntityDescription

    def __init__(self, coordinator: LeetCodeDataUpdateCoordinator) -> None:
        """Use the fixed contests description."""
        super().__init__(coordinator, CONTESTS_DESCRIPTION)

    @property
    def event(self) -> CalendarEvent | None:
        """Return the next upcoming contest, or `None`."""
        contests = self.coordinator.data.upcoming_contests
        if not contests:
            return None
        return _contest_to_event(contests[0])

    async def async_get_events(
        self,
        _hass: HomeAssistant,
        start_date: datetime,
        end_date: datetime,
    ) -> list[CalendarEvent]:
        """Return all upcoming contests that overlap [start_date, end_date]."""
        events: list[CalendarEvent] = []
        for contest in self.coordinator.data.upcoming_contests:
            if contest.end_time < start_date or contest.start_time > end_date:
                continue
            events.append(_contest_to_event(contest))
        return events


class LeetCodeSubmissionsCalendar(LeetCodeUserEntity, CalendarEntity):
    """Per-day "I coded today" calendar derived from the submission calendar."""

    entity_description: CalendarEntityDescription

    def __init__(self, coordinator: LeetCodeDataUpdateCoordinator) -> None:
        """Use the fixed submissions description."""
        super().__init__(coordinator, SUBMISSIONS_DESCRIPTION)

    @property
    def event(self) -> CalendarEvent | None:
        """Return today's submission summary, or the most recent past day."""
        calendar = self.coordinator.data.submission_calendar
        if not calendar:
            return None
        today = datetime.now(tz=UTC).date()
        # Prefer today; otherwise the most recent past day with submissions.
        for day, count in reversed(calendar):
            if day <= today:
                return _day_to_event(day, count, self.coordinator.client.username)
        return None

    async def async_get_events(
        self,
        _hass: HomeAssistant,
        start_date: datetime,
        end_date: datetime,
    ) -> list[CalendarEvent]:
        """Return one all-day event per day with at least one accepted submission."""
        username = self.coordinator.client.username
        events: list[CalendarEvent] = []
        for day, count in self.coordinator.data.submission_calendar:
            day_start = datetime.combine(day, time.min, tzinfo=UTC)
            day_end = datetime.combine(day, time.max, tzinfo=UTC)
            if day_end < start_date or day_start > end_date:
                continue
            events.append(_day_to_event(day, count, username))
        return events


def _contest_to_event(contest: ContestEvent) -> CalendarEvent:
    """Convert a `ContestEvent` to a HA `CalendarEvent`."""
    return CalendarEvent(
        summary=contest.title,
        start=contest.start_time,
        end=contest.end_time,
        location=contest.link,
        description=(
            f"LeetCode contest. {contest.duration_seconds // 60} minutes."
            f"{' Premium-only problems.' if contest.contains_premium else ''}"
        ),
        uid=f"leetcode-contest-{contest.title_slug}",
    )


def _day_to_event(day: date, count: int, username: str) -> CalendarEvent:
    """Build an all-day calendar event for a single day's submission summary."""
    label = "submission" if count == 1 else "submissions"
    return CalendarEvent(
        summary=f"{count} {label}",
        start=day,
        end=day + timedelta(days=1),
        description=f"{username} made {count} accepted {label} on {day.isoformat()}.",
        uid=f"leetcode-submissions-{username}-{day.isoformat()}",
    )
