"""Sensor platform for the LeetCode integration."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from homeassistant.components.sensor import (
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.helpers.typing import StateType

from .api import UserStats
from .entity import LeetCodeGlobalEntity, LeetCodeUserEntity

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant
    from homeassistant.helpers.entity_platform import AddEntitiesCallback

    from . import LeetCodeConfigEntry
    from .coordinator import LeetCodeDataUpdateCoordinator

PARALLEL_UPDATES = 0  # Coordinator pushes data; entity updates make no HTTP calls.


@dataclass(frozen=True, kw_only=True)
class LeetCodeSensorEntityDescription(SensorEntityDescription):
    """Sensor description that knows how to extract its state from `UserStats`."""

    value_fn: Callable[[UserStats], StateType]


HEADLINE_DESCRIPTION = SensorEntityDescription(
    key="user",
    name=None,
    icon="mdi:account-check",
    state_class=SensorStateClass.TOTAL,
    native_unit_of_measurement="problems",
)

DAILY_DESCRIPTION = SensorEntityDescription(
    key="daily_challenge",
    translation_key="daily_challenge",
    icon="mdi:calendar-today",
)

RECENT_SUBMISSIONS_DESCRIPTION = SensorEntityDescription(
    key="recent_submissions",
    translation_key="recent_submissions",
    icon="mdi:history",
    state_class=SensorStateClass.MEASUREMENT,
    native_unit_of_measurement="submissions",
)

TOP_LANGUAGE_DESCRIPTION = SensorEntityDescription(
    key="top_language",
    translation_key="top_language",
    icon="mdi:code-tags",
)

TOP_SKILL_DESCRIPTION = SensorEntityDescription(
    key="top_skill",
    translation_key="top_skill",
    icon="mdi:lightbulb-on",
)

USER_BREAKDOWN_SENSORS: tuple[LeetCodeSensorEntityDescription, ...] = (
    LeetCodeSensorEntityDescription(
        key="easy_solved",
        translation_key="easy_solved",
        icon="mdi:numeric-1-circle",
        state_class=SensorStateClass.TOTAL,
        native_unit_of_measurement="problems",
        value_fn=lambda s: s.easy_solved,
    ),
    LeetCodeSensorEntityDescription(
        key="medium_solved",
        translation_key="medium_solved",
        icon="mdi:numeric-2-circle",
        state_class=SensorStateClass.TOTAL,
        native_unit_of_measurement="problems",
        value_fn=lambda s: s.medium_solved,
    ),
    LeetCodeSensorEntityDescription(
        key="hard_solved",
        translation_key="hard_solved",
        icon="mdi:numeric-3-circle",
        state_class=SensorStateClass.TOTAL,
        native_unit_of_measurement="problems",
        value_fn=lambda s: s.hard_solved,
    ),
    LeetCodeSensorEntityDescription(
        key="contest_rating",
        translation_key="contest_rating",
        icon="mdi:chart-line",
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=0,
        value_fn=lambda s: s.contest_rating,
    ),
)


async def async_setup_entry(
    _hass: HomeAssistant,
    entry: LeetCodeConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the sensor platform from a config entry."""
    coordinator = entry.runtime_data.coordinator
    entities: list[SensorEntity] = [
        LeetCodeHeadlineSensor(coordinator),
        LeetCodeDailyChallengeSensor(coordinator),
        LeetCodeRecentSubmissionsSensor(coordinator),
        LeetCodeTopLanguageSensor(coordinator),
        LeetCodeTopSkillSensor(coordinator),
    ]
    entities.extend(
        LeetCodeBreakdownSensor(coordinator, description) for description in USER_BREAKDOWN_SENSORS
    )
    async_add_entities(entities)


class LeetCodeBreakdownSensor(LeetCodeUserEntity, SensorEntity):
    """Per-metric numeric sensor (easy/medium/hard solved, contest rating)."""

    entity_description: LeetCodeSensorEntityDescription

    @property
    def native_value(self) -> StateType:
        """Return the value derived from the latest `UserStats` snapshot."""
        return self.entity_description.value_fn(self.coordinator.data)


class LeetCodeHeadlineSensor(LeetCodeUserEntity, SensorEntity):
    """Single user-level sensor whose state is total solved.

    Exposes the rest of the user-level metrics (acceptance rate, ranking,
    contest stats, streak, last submission, profile URL) as attributes so
    they can be templated without each one being its own entity.
    """

    def __init__(self, coordinator: LeetCodeDataUpdateCoordinator) -> None:
        """Use a fixed entity description; this sensor is per config entry."""
        super().__init__(coordinator, HEADLINE_DESCRIPTION)

    @property
    def native_value(self) -> int:
        """Return total solved problems."""
        return self.coordinator.data.total_solved

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return all user-level metrics that are not their own sensor."""
        s = self.coordinator.data
        return {
            "username": s.username,
            "profile_url": f"https://leetcode.com/{s.username}/",
            "easy_solved": s.easy_solved,
            "medium_solved": s.medium_solved,
            "hard_solved": s.hard_solved,
            "total_questions": s.total_questions,
            "acceptance_rate": s.acceptance_rate,
            "global_ranking": s.ranking,
            "contest_rating": s.contest_rating,
            "contest_global_ranking": s.contest_global_ranking,
            "contests_attended": s.contests_attended,
            "top_percentage": s.top_percentage,
            "current_streak": s.current_streak,
            "last_submission": (s.last_submission.isoformat() if s.last_submission else None),
        }


class LeetCodeRecentSubmissionsSensor(LeetCodeUserEntity, SensorEntity):
    """List the user's last accepted submissions (state = count)."""

    def __init__(self, coordinator: LeetCodeDataUpdateCoordinator) -> None:
        """Use a fixed description for the recent-submissions sensor."""
        super().__init__(coordinator, RECENT_SUBMISSIONS_DESCRIPTION)

    @property
    def native_value(self) -> int:
        """Return how many submissions are currently held in the buffer."""
        return len(self.coordinator.data.recent_submissions)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Expose the buffer as a list of dicts for use in templates / cards."""
        return {
            "submissions": [
                {
                    "title": s.title,
                    "title_slug": s.title_slug,
                    "language": s.language,
                    "status": s.status,
                    "link": s.link,
                    "timestamp": s.timestamp.isoformat(),
                }
                for s in self.coordinator.data.recent_submissions
            ]
        }


class LeetCodeTopLanguageSensor(LeetCodeUserEntity, SensorEntity):
    """The programming language the user has solved the most problems in."""

    def __init__(self, coordinator: LeetCodeDataUpdateCoordinator) -> None:
        """Use a fixed description for the top-language sensor."""
        super().__init__(coordinator, TOP_LANGUAGE_DESCRIPTION)

    @property
    def native_value(self) -> str | None:
        """Return the dominant language name, or `None` if no submissions yet."""
        top = self.coordinator.data.top_language
        return top.name if top else None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Expose the full per-language breakdown."""
        languages = self.coordinator.data.languages
        return {
            "languages": [
                {"name": lang.name, "problems_solved": lang.problems_solved} for lang in languages
            ]
        }


class LeetCodeTopSkillSensor(LeetCodeUserEntity, SensorEntity):
    """The topic tag the user has solved the most problems in."""

    def __init__(self, coordinator: LeetCodeDataUpdateCoordinator) -> None:
        """Use a fixed description for the top-skill sensor."""
        super().__init__(coordinator, TOP_SKILL_DESCRIPTION)

    @property
    def native_value(self) -> str | None:
        """Return the strongest topic tag's name, or `None` if no skills yet."""
        top = self.coordinator.data.top_skill
        return top.name if top else None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Expose the full per-skill breakdown grouped by tier."""
        skills = self.coordinator.data.skills
        top = self.coordinator.data.top_skill
        return {
            "tier": top.tier if top else None,
            "skills": [
                {
                    "name": skill.name,
                    "slug": skill.slug,
                    "problems_solved": skill.problems_solved,
                    "tier": skill.tier,
                }
                for skill in skills
            ],
        }


class LeetCodeDailyChallengeSensor(LeetCodeGlobalEntity, SensorEntity):
    """Daily LeetCode challenge — global, lives on its own device."""

    def __init__(self, coordinator: LeetCodeDataUpdateCoordinator) -> None:
        """Use the fixed daily-challenge description."""
        super().__init__(coordinator, DAILY_DESCRIPTION)

    @property
    def native_value(self) -> str | None:
        """Return today's challenge title (or `None` if the API omitted it)."""
        return self.coordinator.data.daily_challenge.title or None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return today's challenge metadata."""
        d = self.coordinator.data.daily_challenge
        return {
            "question_id": d.question_id,
            "date": d.date,
            "difficulty": d.difficulty,
            "title_slug": d.title_slug,
            "link": d.link,
            "tags": list(d.tags),
            "is_paid_only": d.is_paid_only,
        }
