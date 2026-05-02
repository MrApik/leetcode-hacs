"""Config and options flows for the LeetCode integration."""

from __future__ import annotations

from collections.abc import Mapping
from typing import TYPE_CHECKING, Any

import voluptuous as vol
from yarl import URL
from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlow,
)
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.selector import (
    NumberSelector,
    NumberSelectorConfig,
    NumberSelectorMode,
    TextSelector,
    TextSelectorConfig,
    TextSelectorType,
)

from .api import (
    LeetCodeApiClient,
    LeetCodeApiError,
    LeetCodeAuthError,
    LeetCodeRateLimitError,
)
from .const import (
    CONF_BASE_URL,
    CONF_SCAN_INTERVAL,
    CONF_STREAK_WARNING_HOUR,
    CONF_USERNAME,
    DEFAULT_BASE_URL,
    DEFAULT_SCAN_INTERVAL,
    DEFAULT_STREAK_WARNING_HOUR,
    DOMAIN,
    MIN_SCAN_INTERVAL,
)

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant

USER_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_USERNAME): TextSelector(
            TextSelectorConfig(type=TextSelectorType.TEXT, autocomplete="username")
        ),
        vol.Optional(CONF_BASE_URL, default=DEFAULT_BASE_URL): TextSelector(
            TextSelectorConfig(type=TextSelectorType.URL)
        ),
    }
)

REAUTH_SCHEMA = vol.Schema(
    {vol.Required(CONF_USERNAME): TextSelector(TextSelectorConfig(autocomplete="username"))}
)


async def _validate_user(
    hass: HomeAssistant, *, username: str, base_url: str
) -> dict[str, str]:
    """Run the username/base-url combination through the API."""
    session = async_get_clientsession(hass)
    client = LeetCodeApiClient(session, base_url=base_url, username=username)
    try:
        await client.async_validate()
    except LeetCodeAuthError:
        return {CONF_USERNAME: "unknown_user"}
    except LeetCodeRateLimitError:
        return {"base": "rate_limited"}
    except LeetCodeApiError:
        return {"base": "cannot_connect"}
    return {}


class LeetCodeConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle initial setup, reauth, and reconfigure flows."""

    VERSION = 1
    MINOR_VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the manual user-initiated setup step."""
        errors: dict[str, str] = {}
        if user_input is not None:
            username = user_input[CONF_USERNAME].strip()
            base_url = user_input.get(CONF_BASE_URL, DEFAULT_BASE_URL).strip()

            await self.async_set_unique_id(_unique_id(base_url, username))
            self._abort_if_unique_id_configured()

            errors = await _validate_user(self.hass, username=username, base_url=base_url)
            if not errors:
                return self.async_create_entry(
                    title=username,
                    data={CONF_USERNAME: username, CONF_BASE_URL: base_url},
                )

        return self.async_show_form(step_id="user", data_schema=USER_SCHEMA, errors=errors)

    async def async_step_reauth(
        self, entry_data: Mapping[str, Any]
    ) -> ConfigFlowResult:
        """Trigger when an existing entry needs new credentials."""
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Ask the user to re-confirm or change the username."""
        entry = self._get_reauth_entry()
        errors: dict[str, str] = {}
        if user_input is not None:
            username = user_input[CONF_USERNAME].strip()
            base_url = entry.data.get(CONF_BASE_URL, DEFAULT_BASE_URL)
            errors = await _validate_user(self.hass, username=username, base_url=base_url)
            if not errors:
                return self.async_update_reload_and_abort(
                    entry,
                    data_updates={CONF_USERNAME: username},
                    unique_id=_unique_id(base_url, username),
                )

        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=self.add_suggested_values_to_schema(
                REAUTH_SCHEMA, {CONF_USERNAME: entry.data.get(CONF_USERNAME)}
            ),
            errors=errors,
        )

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Allow the user to change the username and/or base URL post-setup."""
        entry = self._get_reconfigure_entry()
        errors: dict[str, str] = {}
        if user_input is not None:
            username = user_input[CONF_USERNAME].strip()
            base_url = user_input.get(CONF_BASE_URL, DEFAULT_BASE_URL).strip()
            new_unique_id = _unique_id(base_url, username)
            if new_unique_id != entry.unique_id:
                await self.async_set_unique_id(new_unique_id)
                self._abort_if_unique_id_mismatch()
            errors = await _validate_user(self.hass, username=username, base_url=base_url)
            if not errors:
                return self.async_update_reload_and_abort(
                    entry,
                    data_updates={CONF_USERNAME: username, CONF_BASE_URL: base_url},
                    unique_id=new_unique_id,
                    title=username,
                )

        return self.async_show_form(
            step_id="reconfigure",
            data_schema=self.add_suggested_values_to_schema(USER_SCHEMA, dict(entry.data)),
            errors=errors,
        )

    @staticmethod
    def async_get_options_flow(config_entry: ConfigEntry) -> OptionsFlow:
        """Return the options-flow handler."""
        return LeetCodeOptionsFlow()


class LeetCodeOptionsFlow(OptionsFlow):
    """Lets the user adjust polling and streak-warning options after setup."""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Show / handle the options form."""
        if user_input is not None:
            return self.async_create_entry(data=user_input)

        current_interval = self.config_entry.options.get(
            CONF_SCAN_INTERVAL, int(DEFAULT_SCAN_INTERVAL.total_seconds())
        )
        current_warning_hour = self.config_entry.options.get(
            CONF_STREAK_WARNING_HOUR, DEFAULT_STREAK_WARNING_HOUR
        )
        schema = vol.Schema(
            {
                vol.Required(
                    CONF_SCAN_INTERVAL, default=current_interval
                ): NumberSelector(
                    NumberSelectorConfig(
                        min=int(MIN_SCAN_INTERVAL.total_seconds()),
                        max=24 * 60 * 60,
                        step=60,
                        unit_of_measurement="s",
                        mode=NumberSelectorMode.BOX,
                    )
                ),
                vol.Required(
                    CONF_STREAK_WARNING_HOUR, default=current_warning_hour
                ): NumberSelector(
                    NumberSelectorConfig(
                        min=0,
                        max=23,
                        step=1,
                        unit_of_measurement="h",
                        mode=NumberSelectorMode.SLIDER,
                    )
                ),
            }
        )
        return self.async_show_form(step_id="init", data_schema=schema)


def _unique_id(base_url: str, username: str) -> str:
    """Build a stable unique-id from the base URL host plus username (case-insensitive)."""
    host = (URL(base_url).host or base_url).lower()
    return f"{host}::{username.lower()}"
