"""Constants for the LeetCode integration."""

from __future__ import annotations

from datetime import timedelta
from typing import Final

DOMAIN: Final = "leetcode_hacs"
MANUFACTURER: Final = "LeetCode"

CONF_USERNAME: Final = "username"
CONF_BASE_URL: Final = "base_url"
CONF_SCAN_INTERVAL: Final = "scan_interval"
CONF_STREAK_WARNING_HOUR: Final = "streak_warning_hour"

DEFAULT_BASE_URL: Final = "https://alfa-leetcode-api.onrender.com"
DEFAULT_SCAN_INTERVAL: Final = timedelta(minutes=15)
MIN_SCAN_INTERVAL: Final = timedelta(minutes=5)
DEFAULT_STREAK_WARNING_HOUR: Final = 20  # 8 PM in the user's local timezone
REQUEST_TIMEOUT: Final = 30  # seconds

EVENT_PROBLEM_SOLVED: Final = "leetcode_hacs_problem_solved"
EVENT_STREAK_MILESTONE: Final = "leetcode_hacs_streak_milestone"
STREAK_MILESTONES: Final = (7, 30, 100, 365, 730, 1000)

SERVICE_REFRESH: Final = "refresh"
SERVICE_FETCH_PROBLEM: Final = "fetch_problem"
