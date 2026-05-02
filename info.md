# LeetCode

Surfaces your LeetCode statistics in Home Assistant: problems solved by
difficulty, contest rating, current streak, last submission, and the
daily challenge — all driven by the community
[alfa-leetcode-api](https://github.com/alfaarghya/alfa-leetcode-api).

## What you get

- A **per-user device** with a headline sensor (total solved) plus
  separate sensors for easy / medium / hard / contest rating, and a
  binary sensor that flips on once you've solved today's daily challenge.
- A **shared "LeetCode Daily Challenge" device** with the day's puzzle —
  title, link, topic tags, problem ID, difficulty.
- A **`leetcode_hacs.refresh` action** so you can pull fresh data
  immediately after solving a problem.

## Configuration

UI-only — no YAML. After install, **Settings → Devices & Services →
Add Integration → LeetCode**, enter your username, optionally point at a
self-hosted alfa-leetcode-api instance.

The default public API is rate-limited to 120 requests/hour/IP, so the
default 15-minute polling interval keeps you well under that ceiling.

See the [README](https://github.com/MrApik/leetcode-hacs#readme) for the
full entity list, troubleshooting, and self-hosting instructions.
