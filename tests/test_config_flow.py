"""Tests for the LeetCode config and options flows."""

from __future__ import annotations

from typing import Any
from unittest.mock import patch

import pytest
from aioresponses import aioresponses
from custom_components.leetcode_hacs.const import (
    CONF_BASE_URL,
    CONF_SCAN_INTERVAL,
    DOMAIN,
)
from homeassistant import config_entries
from homeassistant.const import CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from pytest_homeassistant_custom_component.common import MockConfigEntry

from .const import TEST_BASE_URL, TEST_USERNAME, USER_INPUT

pytestmark = pytest.mark.asyncio


async def _start_user_flow(hass: HomeAssistant, user_input: dict[str, Any] | None = None) -> Any:
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    if user_input is None:
        return result
    return await hass.config_entries.flow.async_configure(result["flow_id"], user_input)


async def test_user_flow_success(hass: HomeAssistant, stub_api: aioresponses) -> None:
    """A valid username + base URL produces a config entry."""
    with patch(
        "custom_components.leetcode_hacs.async_setup_entry", return_value=True
    ) as mock_setup:
        result = await _start_user_flow(hass, USER_INPUT)

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == TEST_USERNAME
    assert result["data"] == {CONF_USERNAME: TEST_USERNAME, CONF_BASE_URL: TEST_BASE_URL}
    mock_setup.assert_awaited_once()


async def test_user_flow_unknown_user(hass: HomeAssistant, mock_aioresponse: aioresponses) -> None:
    """A 404 from the API surfaces the `unknown_user` error key."""
    mock_aioresponse.get(f"{TEST_BASE_URL}/{TEST_USERNAME}", status=404)
    result = await _start_user_flow(hass, USER_INPUT)

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {CONF_USERNAME: "unknown_user"}


async def test_user_flow_rate_limited(hass: HomeAssistant, mock_aioresponse: aioresponses) -> None:
    """A 429 surfaces the `rate_limited` error key on the form base."""
    mock_aioresponse.get(f"{TEST_BASE_URL}/{TEST_USERNAME}", status=429)
    result = await _start_user_flow(hass, USER_INPUT)

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "rate_limited"}


async def test_user_flow_cannot_connect(
    hass: HomeAssistant, mock_aioresponse: aioresponses
) -> None:
    """Other transport errors surface `cannot_connect`."""
    mock_aioresponse.get(f"{TEST_BASE_URL}/{TEST_USERNAME}", status=500)
    result = await _start_user_flow(hass, USER_INPUT)

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "cannot_connect"}


async def test_user_flow_duplicate_aborts(
    hass: HomeAssistant,
    stub_api: aioresponses,
    config_entry: MockConfigEntry,
) -> None:
    """Adding the same profile twice aborts via the unique-id check."""
    config_entry.add_to_hass(hass)
    result = await _start_user_flow(hass, USER_INPUT)

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_reauth_flow(
    hass: HomeAssistant, stub_api: aioresponses, config_entry: MockConfigEntry
) -> None:
    """The reauth flow updates the username and reloads the entry."""
    config_entry.add_to_hass(hass)
    result = await config_entry.start_reauth_flow(hass)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reauth_confirm"

    new_username = "newcoder"
    stub_api.get(f"{TEST_BASE_URL}/{new_username}", payload={"username": new_username})

    with patch("custom_components.leetcode_hacs.async_setup_entry", return_value=True):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {CONF_USERNAME: new_username}
        )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"
    assert config_entry.data[CONF_USERNAME] == new_username


async def test_reconfigure_flow(
    hass: HomeAssistant, stub_api: aioresponses, config_entry: MockConfigEntry
) -> None:
    """The reconfigure flow updates both username and base URL."""
    config_entry.add_to_hass(hass)
    result = await config_entry.start_reconfigure_flow(hass)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reconfigure"

    new_username = "newcoder"
    new_url = "https://self-hosted.example"
    stub_api.get(f"{new_url}/{new_username}", payload={"username": new_username})

    with patch("custom_components.leetcode_hacs.async_setup_entry", return_value=True):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_USERNAME: new_username, CONF_BASE_URL: new_url},
        )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"
    assert config_entry.data[CONF_USERNAME] == new_username
    assert config_entry.data[CONF_BASE_URL] == new_url


async def test_options_flow(
    hass: HomeAssistant, stub_api: aioresponses, config_entry: MockConfigEntry
) -> None:
    """The options flow stores the polling interval."""
    config_entry.add_to_hass(hass)
    with patch("custom_components.leetcode_hacs.async_setup_entry", return_value=True):
        result = await hass.config_entries.options.async_init(config_entry.entry_id)
        assert result["type"] is FlowResultType.FORM

        result = await hass.config_entries.options.async_configure(
            result["flow_id"], {CONF_SCAN_INTERVAL: 600}
        )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    # The form's `streak_warning_hour` field has a default that voluptuous
    # fills in even when the caller only passes `scan_interval`.
    assert result["data"][CONF_SCAN_INTERVAL] == 600
    assert "streak_warning_hour" in result["data"]
