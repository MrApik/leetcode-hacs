# LeetCode Home Assistant Addon

[![GitHub Release](https://img.shields.io/github/v/release/MrApik/leetcode-hacs?display_name=tag&sort=semver)](https://github.com/MrApik/leetcode-hacs/releases)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![HACS Custom](https://img.shields.io/badge/HACS-Custom-41BDF5.svg)](https://github.com/hacs/integration)
[![Validate](https://github.com/MrApik/leetcode-hacs/actions/workflows/validate.yml/badge.svg)](https://github.com/MrApik/leetcode-hacs/actions/workflows/validate.yml)
[![Tests](https://github.com/MrApik/leetcode-hacs/actions/workflows/tests.yml/badge.svg)](https://github.com/MrApik/leetcode-hacs/actions/workflows/tests.yml)
[![Coverage](https://codecov.io/gh/MrApik/leetcode-hacs/branch/master/graph/badge.svg)](https://codecov.io/gh/MrApik/leetcode-hacs)

[![Open your Home Assistant instance and open a repository inside the Home Assistant Community Store.](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=MrApik&repository=leetcode-hacs&category=integration)

A Home Assistant custom integration that exposes LeetCode statistics -
problems solved, contest rating, daily challenge, current streak - as
sensors and a binary sensor.

Each configured account is represented by two devices: a per-user
**LeetCode &lt;username&gt;** device for personal stats, and a shared
**LeetCode Daily Challenge** device for the day's puzzle (which is the
same for every LeetCode user).

Data is sourced from the community
[alfa-leetcode-api](https://github.com/alfaarghya/alfa-leetcode-api). You
can use the public hosted instance or point the integration at a
self-hosted one.

## Features

- UI configuration - no YAML required.
- Reauthentication and reconfiguration from the UI.
- Configurable polling interval and API base URL.
- Diagnostics download with credentials redacted.

## Entities

Two devices are created per configured account:

- **`LeetCode <username>`** - your personal sensors.
- **`LeetCode`** - global data (today's daily challenge, upcoming contests).

### Per-user device

| Entity | State | Notes |
| --- | --- | --- |
| `sensor.leetcode_<user>` | Total problems solved | Headline sensor. Attributes: `profile_url`, `acceptance_rate`, `global_ranking`, `contest_rating`, `contest_global_ranking`, `contests_attended`, `top_percentage`, `current_streak`, `last_submission`, plus the per-difficulty solved counts. |
| `sensor.leetcode_<user>_easy_solved` | Easy problems solved | |
| `sensor.leetcode_<user>_medium_solved` | Medium problems solved | |
| `sensor.leetcode_<user>_hard_solved` | Hard problems solved | |
| `sensor.leetcode_<user>_contest_rating` | Contest rating | |
| `sensor.leetcode_<user>_recent_submissions` | Number of accepted submissions in the buffer (10 most recent) | Attribute `submissions` is a list of `{title, title_slug, language, status, link, timestamp}`. |
| `sensor.leetcode_<user>_top_language` | Most-used programming language | Attribute `languages` is the full per-language breakdown. |
| `sensor.leetcode_<user>_top_skill` | Strongest topic tag (e.g. `Array`) | Attribute `tier` is `fundamental`/`intermediate`/`advanced`; `skills` is the full breakdown. |
| `binary_sensor.leetcode_<user>_daily_challenge_solved` | `on` if today's daily is solved | Attributes: `title`, `difficulty`, `link`, `date`. |
| `binary_sensor.leetcode_<user>_streak_at_risk` | `on` after the configured warning hour if you have a streak and have not yet submitted today | Attributes: `current_streak`, `last_submission`, `warning_hour`. |
| `calendar.leetcode_<user>_submissions` | Per-day "I coded today" history | All-day events for each day with at least one accepted submission. |

### Global device

| Entity | State | Notes |
| --- | --- | --- |
| `sensor.leetcode_daily_challenge` | Today's challenge title | Attributes: `question_id` (the displayed problem number, e.g. `"1"` for *Two Sum*), `link`, `title_slug`, `difficulty`, `date`, `tags` (list of LeetCode topic tags such as `Array`, `Hash Table`), `is_paid_only`. |
| `calendar.leetcode_contests` | Next upcoming LeetCode contest | Calendar entries for all known upcoming Weekly / Biweekly contests. |

### Profile and challenge links

- The user's profile page (`https://leetcode.com/<user>/`) is the per-user
  device's **Visit device** link, *and* the `profile_url` attribute on the
  headline sensor.
- The daily challenge URL is the `link` attribute on both
  `sensor.leetcode_daily_challenge` and the per-user
  `binary_sensor.leetcode_<user>_daily_challenge_solved`.

## Actions

| Action | Description |
| --- | --- |
| `leetcode_hacs.refresh` | Refresh data immediately, bypassing the polling interval. Optionally targets a single profile via the `entry_id` field; otherwise refreshes every configured profile. |
| `leetcode_hacs.fetch_problem` | Fetch a single problem's metadata by its `title_slug`. Returns `{title, title_slug, question_id, difficulty, is_paid_only, link, tags, hints, likes, dislikes}` as a service response - usable from scripts, automations, TTS. |

## Events

| Event | Fired when | Payload |
| --- | --- | --- |
| `leetcode_hacs_problem_solved` | The user's `total_solved` count goes up between refreshes | `username`, `previous_total`, `current_total`, `delta`, `newest_submission` (object with `title`, `title_slug`, `link`, `language`, `timestamp`) |
| `leetcode_hacs_streak_milestone` | The user's streak crosses 7, 30, 100, 365, 730, or 1000 days | `username`, `milestone`, `current_streak` |

## Installation

### HACS (recommended)

1. Click the **Open in HACS** badge at the top of this README (or open
   HACS → ⋮ → **Custom repositories** and add
   `https://github.com/MrApik/leetcode-hacs` with category **Integration**).
2. Install **LeetCode**, then restart Home Assistant.
3. Add the integration:

   [![Open your Home Assistant instance and start setting up a new integration.](https://my.home-assistant.io/badges/config_flow_start.svg)](https://my.home-assistant.io/redirect/config_flow_start/?domain=leetcode_hacs)

   …or **Settings → Devices & Services → Add Integration** and search
   for *LeetCode*.

### Manual

Copy `custom_components/leetcode_hacs/` into your Home Assistant
`config/custom_components/` directory and restart, then add the
integration via **Settings → Devices & Services → Add Integration**.

## Configuration

| Field | Default | Notes |
| --- | --- | --- |
| Username | - | LeetCode username (case-sensitive). |
| API base URL | `https://alfa-leetcode-api.onrender.com` | Override to point at a self-hosted alfa-leetcode-api instance. |
| Polling interval | 15 minutes | Minimum 5 minutes (matches the upstream API's response cache). |
| Streak-warning hour | 20 (8 PM, local time) | Hour after which `binary_sensor.leetcode_<user>_streak_at_risk` flips on if no submission has been made today. |

The default public instance is rate-limited to 120 requests per IP per
hour; the default polling interval keeps the integration well under that
ceiling.

The polling interval and streak-warning hour are exposed via
**Settings → Devices & Services → LeetCode → Configure**.

## Self-hosting alfa-leetcode-api

```bash
docker run -d --name alfa-leetcode-api -p 3000:3000 \
  alfaarghya/alfa-leetcode-api:2.0.4
```

Then set **API base URL** to `http://<host>:3000` when configuring the
integration.

## Troubleshooting

- **`unknown_user` on setup** - double-check the case of your LeetCode
  username; the API treats it as case-sensitive.
- **`rate_limited` on setup** - the public instance is shared and capped
  at 120 requests per IP per hour. Wait an hour or self-host.
- **Stale data** - the upstream API caches responses for 5 minutes, so a
  newly solved problem may take that long to appear regardless of the
  polling interval.

For anything else, download diagnostics from
**Settings → Devices & Services → LeetCode → ⋮ → Download diagnostics**
and attach them to a [new issue](https://github.com/MrApik/leetcode-hacs/issues/new/choose).

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md).

## License

[MIT](LICENSE).

## Acknowledgements

- [alfa-leetcode-api](https://github.com/alfaarghya/alfa-leetcode-api)
  by [@alfaarghya](https://github.com/alfaarghya) - the API this
  integration consumes.
- This project is **not** affiliated with LeetCode.
