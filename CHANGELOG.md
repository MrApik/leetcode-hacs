# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.1.2] - 2026-05-02

### Fixed

- Easy / medium / hard / total-solved counts (and the headline sensor)
  always read as zero. The integration was pulling these from the
  `/<user>` endpoint, which returns only avatar / ranking metadata; the
  counts live on `/<user>/profile`. The client now uses `/<user>/profile`
  for both validation and refreshes, and acceptance rate is derived from
  `matchedUserStats` since `/<user>/profile` doesn't expose it directly.

## [0.1.1] - 2026-05-02

### Fixed

- API client built malformed URLs (`https://host//path`) when the base URL
  had no path component, so the first refresh always failed.
- The reconfigure flow now allows changing the username or API base URL;
  it previously aborted with `unique_id_mismatch` because the entry's
  unique-id is derived from those fields.

### Added

- `http` declared as an integration dependency so the calendar platform
  is set up reliably alongside the integration.

## [0.1.0] - 2026-05-02

### Added

- Initial release.

[Unreleased]: https://github.com/MrApik/leetcode-hacs/compare/v0.1.2...HEAD
[0.1.2]: https://github.com/MrApik/leetcode-hacs/releases/tag/v0.1.2
[0.1.1]: https://github.com/MrApik/leetcode-hacs/releases/tag/v0.1.1
[0.1.0]: https://github.com/MrApik/leetcode-hacs/releases/tag/v0.1.0
