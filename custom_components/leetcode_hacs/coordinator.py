"""DataUpdateCoordinator for the LeetCode integration."""

from __future__ import annotations

import logging
from datetime import timedelta
from typing import TYPE_CHECKING

from homeassistant.config_entries import ConfigEntry
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import (
    LeetCodeApiClient,
    LeetCodeApiError,
    LeetCodeAuthError,
    LeetCodeRateLimitError,
    UserStats,
)
from .const import (
    DOMAIN,
    EVENT_PROBLEM_SOLVED,
    EVENT_STREAK_MILESTONE,
    STREAK_MILESTONES,
)

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant

_LOGGER = logging.getLogger(__name__)


class LeetCodeDataUpdateCoordinator(DataUpdateCoordinator[UserStats]):
    """Coordinator that periodically refreshes a user's LeetCode statistics."""

    config_entry: ConfigEntry

    def __init__(
        self,
        hass: HomeAssistant,
        config_entry: ConfigEntry,
        client: LeetCodeApiClient,
        update_interval: timedelta,
    ) -> None:
        """Create a coordinator bound to a single config entry."""
        super().__init__(
            hass,
            _LOGGER,
            name=f"{DOMAIN}_{client.username}",
            update_interval=update_interval,
            config_entry=config_entry,
            always_update=False,
        )
        self.client = client
        self._previous: UserStats | None = None

    async def _async_update_data(self) -> UserStats:
        """Fetch the latest data, mapping errors to HA-recognised exceptions."""
        try:
            new_data = await self.client.async_fetch_stats()
        except LeetCodeAuthError as err:
            raise ConfigEntryAuthFailed(str(err)) from err
        except LeetCodeRateLimitError as err:
            raise UpdateFailed(str(err)) from err
        except LeetCodeApiError as err:
            raise UpdateFailed(str(err)) from err

        self._maybe_fire_events(new_data)
        self._previous = new_data
        return new_data

    def _maybe_fire_events(self, new: UserStats) -> None:
        """Fire automation-friendly events when key counters advance."""
        previous = self._previous
        if previous is None:
            # First refresh — establish baselines silently.
            return

        if new.total_solved > previous.total_solved:
            newest = new.recent_submissions[0] if new.recent_submissions else None
            self.hass.bus.async_fire(
                EVENT_PROBLEM_SOLVED,
                {
                    "username": new.username,
                    "previous_total": previous.total_solved,
                    "current_total": new.total_solved,
                    "delta": new.total_solved - previous.total_solved,
                    "newest_submission": (
                        {
                            "title": newest.title,
                            "title_slug": newest.title_slug,
                            "link": newest.link,
                            "language": newest.language,
                            "timestamp": newest.timestamp.isoformat(),
                        }
                        if newest is not None
                        else None
                    ),
                },
            )

        if new.current_streak > previous.current_streak:
            for milestone in STREAK_MILESTONES:
                if previous.current_streak < milestone <= new.current_streak:
                    self.hass.bus.async_fire(
                        EVENT_STREAK_MILESTONE,
                        {
                            "username": new.username,
                            "milestone": milestone,
                            "current_streak": new.current_streak,
                        },
                    )
