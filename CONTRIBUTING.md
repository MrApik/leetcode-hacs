# Contributing

## Development environment

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
pre-commit install
```

`pyproject.toml` pins a Home Assistant Core version, so the test suite
runs against the same APIs the integration uses at runtime.

## Running the checks

```bash
ruff check .
ruff format --check .
mypy custom_components
pytest
```

The same checks run in CI on every push and pull request.

## Validating the integration

Two GitHub Actions run on every PR:

- `home-assistant/actions/hassfest@master` — validates `manifest.json`,
  translations, and services.
- `hacs/action@master` — validates HACS publishing requirements.

To run hassfest locally, check out
[home-assistant/core](https://github.com/home-assistant/core) and run
`python -m script.hassfest --integration-path custom_components/leetcode_hacs`.

## Pull-request checklist

- The change is covered by a test.
- `pytest --cov=custom_components.leetcode_hacs` keeps coverage above 95 %.
- New user-visible strings are added to `translations/en.json`.
- `CHANGELOG.md` has an entry under `[Unreleased]`.

## Reporting issues

Use the templates under `.github/ISSUE_TEMPLATE/`. Diagnostics output
(Settings → Devices & Services → LeetCode → ⋮ → Download diagnostics)
helps a lot — credentials are redacted automatically.

## Releasing

1. Bump `version` in `custom_components/leetcode_hacs/manifest.json` and
   `pyproject.toml`.
2. Move the relevant `CHANGELOG.md` entries from `[Unreleased]` to a new
   version section.
3. Tag the commit `vX.Y.Z` and publish a GitHub release. The release
   workflow verifies the manifest version matches the tag and attaches a
   `leetcode_hacs.zip` artefact.

## Code of conduct

This project follows the
[Contributor Covenant](https://www.contributor-covenant.org/version/2/1/code_of_conduct/).
