"""Binary-sensor platform for the LeetCode integration."""

from __future__ import annotations

from typing import TYPE_CHECKING

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.util import dt as dt_util

from .const import CONF_STREAK_WARNING_HOUR, DEFAULT_STREAK_WARNING_HOUR
from .entity import LeetCodeUserEntity

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant
    from homeassistant.helpers.entity_platform import AddEntitiesCallback

    from . import LeetCodeConfigEntry

PARALLEL_UPDATES = 0  # Coordinator pushes data; entity updates make no HTTP calls.

DAILY_SOLVED_DESCRIPTION = BinarySensorEntityDescription(
    key="daily_challenge_solved",
    translation_key="daily_challenge_solved",
    icon="mdi:calendar-check",
)

STREAK_AT_RISK_DESCRIPTION = BinarySensorEntityDescription(
    key="streak_at_risk",
    translation_key="streak_at_risk",
    icon="mdi:fire-alert",
    device_class=BinarySensorDeviceClass.PROBLEM,
)


async def async_setup_entry(
    _hass: HomeAssistant,
    entry: LeetCodeConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the binary-sensor platform from a config entry."""
    coordinator = entry.runtime_data.coordinator
    async_add_entities(
        [
            LeetCodeDailySolvedBinarySensor(coordinator, DAILY_SOLVED_DESCRIPTION),
            LeetCodeStreakAtRiskBinarySensor(coordinator, STREAK_AT_RISK_DESCRIPTION),
        ]
    )


class LeetCodeDailySolvedBinarySensor(LeetCodeUserEntity, BinarySensorEntity):
    """True iff the user has solved today's daily challenge."""

    entity_description: BinarySensorEntityDescription

    @property
    def is_on(self) -> bool:
        """Return whether today's daily challenge has been solved."""
        return self.coordinator.data.daily_solved

    @property
    def extra_state_attributes(self) -> dict[str, str]:
        """Expose the daily-challenge metadata for automations and cards."""
        daily = self.coordinator.data.daily_challenge
        return {
            "date": daily.date,
            "title": daily.title,
            "difficulty": daily.difficulty,
            "link": daily.link,
        }


class LeetCodeStreakAtRiskBinarySensor(LeetCodeUserEntity, BinarySensorEntity):
    """True when the user has an active streak that they have not yet defended today.

    Becomes `on` once the local time of day reaches the configured warning
    hour (default 8 PM) and the user has not submitted a problem today.
    """

    entity_description: BinarySensorEntityDescription

    @property
    def is_on(self) -> bool:
        """Return whether the streak is currently at risk."""
        s = self.coordinator.data
        if s.current_streak == 0:
            return False
        local_now = dt_util.now()
        today = local_now.date()
        if s.last_submission is not None:
            local_last = s.last_submission.astimezone(local_now.tzinfo)
            if local_last.date() == today:
                return False
        warning_hour = self.coordinator.config_entry.options.get(
            CONF_STREAK_WARNING_HOUR, DEFAULT_STREAK_WARNING_HOUR
        )
        return local_now.hour >= int(warning_hour)

    @property
    def extra_state_attributes(self) -> dict[str, int | str | None]:
        """Expose the underlying signals so users can build richer automations."""
        s = self.coordinator.data
        warning_hour = self.coordinator.config_entry.options.get(
            CONF_STREAK_WARNING_HOUR, DEFAULT_STREAK_WARNING_HOUR
        )
        return {
            "current_streak": s.current_streak,
            "last_submission": (s.last_submission.isoformat() if s.last_submission else None),
            "warning_hour": int(warning_hour),
        }
