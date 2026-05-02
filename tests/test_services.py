"""Tests for the integration's actions / services."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest
from aioresponses import aioresponses
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ServiceValidationError
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.leetcode_hacs.const import (
    DOMAIN,
    SERVICE_FETCH_PROBLEM,
    SERVICE_REFRESH,
)

pytestmark = pytest.mark.asyncio


async def _setup(hass: HomeAssistant, config_entry: MockConfigEntry) -> None:
    config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()


async def test_refresh_service_targets_all_entries(
    hass: HomeAssistant,
    stub_api: aioresponses,  # noqa: ARG001
    config_entry: MockConfigEntry,
) -> None:
    """Calling the action with no `entry_id` refreshes every configured profile."""
    await _setup(hass, config_entry)
    coordinator = config_entry.runtime_data.coordinator

    with patch.object(
        coordinator, "async_request_refresh", new=AsyncMock()
    ) as mock_refresh:
        await hass.services.async_call(DOMAIN, SERVICE_REFRESH, {}, blocking=True)
    mock_refresh.assert_awaited_once()


async def test_refresh_service_targets_single_entry(
    hass: HomeAssistant,
    stub_api: aioresponses,  # noqa: ARG001
    config_entry: MockConfigEntry,
) -> None:
    """Passing `entry_id` refreshes only that profile."""
    await _setup(hass, config_entry)
    coordinator = config_entry.runtime_data.coordinator

    with patch.object(
        coordinator, "async_request_refresh", new=AsyncMock()
    ) as mock_refresh:
        await hass.services.async_call(
            DOMAIN,
            SERVICE_REFRESH,
            {"entry_id": config_entry.entry_id},
            blocking=True,
        )
    mock_refresh.assert_awaited_once()


async def test_refresh_service_ignores_unknown_entry_id(
    hass: HomeAssistant,
    stub_api: aioresponses,  # noqa: ARG001
    config_entry: MockConfigEntry,
) -> None:
    """An unknown `entry_id` is silently ignored — no entries to refresh."""
    await _setup(hass, config_entry)
    coordinator = config_entry.runtime_data.coordinator

    with patch.object(
        coordinator, "async_request_refresh", new=AsyncMock()
    ) as mock_refresh:
        await hass.services.async_call(
            DOMAIN,
            SERVICE_REFRESH,
            {"entry_id": "does-not-exist"},
            blocking=True,
        )
    mock_refresh.assert_not_awaited()


async def test_fetch_problem_service_returns_metadata(
    hass: HomeAssistant,
    stub_api: aioresponses,  # noqa: ARG001
    config_entry: MockConfigEntry,
) -> None:
    """The `fetch_problem` service returns problem metadata as a service response."""
    await _setup(hass, config_entry)
    response = await hass.services.async_call(
        DOMAIN,
        SERVICE_FETCH_PROBLEM,
        {"title_slug": "two-sum"},
        blocking=True,
        return_response=True,
    )
    assert response is not None
    assert response["title"] == "Two Sum"
    assert response["question_id"] == "1"
    assert response["difficulty"] == "easy"
    assert response["link"] == "https://leetcode.com/problems/two-sum/"
    assert "Array" in response["tags"]
    assert len(response["hints"]) == 2


async def test_fetch_problem_without_configured_entry(
    hass: HomeAssistant,
) -> None:
    """Calling `fetch_problem` with no configured profile raises ServiceValidationError."""
    # Force-register the integration without setting up an entry, so the service
    # has to look up entries and find none.
    from custom_components.leetcode_hacs import _async_register_services

    _async_register_services(hass)
    with pytest.raises(ServiceValidationError):
        await hass.services.async_call(
            DOMAIN,
            SERVICE_FETCH_PROBLEM,
            {"title_slug": "two-sum"},
            blocking=True,
            return_response=True,
        )
