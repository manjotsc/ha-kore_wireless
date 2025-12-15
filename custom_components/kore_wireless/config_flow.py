"""Config flow for Kore Wireless SuperSIM integration."""
from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol

from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlowWithConfigEntry,
)
from homeassistant.const import CONF_SCAN_INTERVAL
from homeassistant.core import callback
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.selector import (
    NumberSelector,
    NumberSelectorConfig,
    NumberSelectorMode,
    TextSelector,
    TextSelectorConfig,
    TextSelectorType,
)

from .api import KoreWirelessAPI, KoreWirelessAuthError, KoreWirelessConnectionError
from .const import (
    CONF_API_TOKEN,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_API_TOKEN): TextSelector(
            TextSelectorConfig(type=TextSelectorType.PASSWORD)
        ),
    }
)

STEP_REAUTH_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_API_TOKEN): TextSelector(
            TextSelectorConfig(type=TextSelectorType.PASSWORD)
        ),
    }
)


class KoreWirelessConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Kore Wireless SuperSIM."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialize the config flow."""
        self._reauth_entry: ConfigEntry | None = None

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}

        if user_input is not None:
            api_token = user_input[CONF_API_TOKEN]

            try:
                account_info = await self._test_credentials(api_token)
            except KoreWirelessAuthError:
                errors["base"] = "invalid_auth"
            except KoreWirelessConnectionError:
                errors["base"] = "cannot_connect"
            except Exception:
                _LOGGER.exception("Unexpected exception during setup")
                errors["base"] = "unknown"
            else:
                # Use account SID or first part of token as unique ID
                unique_id = account_info.get("account_sid") or api_token[:16]
                await self.async_set_unique_id(unique_id)
                self._abort_if_unique_id_configured()

                return self.async_create_entry(
                    title="Kore Wireless SuperSIM",
                    data={CONF_API_TOKEN: api_token},
                    options={CONF_SCAN_INTERVAL: DEFAULT_SCAN_INTERVAL},
                )

        return self.async_show_form(
            step_id="user",
            data_schema=STEP_USER_DATA_SCHEMA,
            errors=errors,
        )

    async def async_step_reauth(
        self, entry_data: dict[str, Any]
    ) -> ConfigFlowResult:
        """Handle reauthorization request."""
        self._reauth_entry = self.hass.config_entries.async_get_entry(
            self.context["entry_id"]
        )
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle reauthorization confirmation."""
        errors: dict[str, str] = {}

        if user_input is not None:
            api_token = user_input[CONF_API_TOKEN]

            try:
                await self._test_credentials(api_token)
            except KoreWirelessAuthError:
                errors["base"] = "invalid_auth"
            except KoreWirelessConnectionError:
                errors["base"] = "cannot_connect"
            except Exception:
                _LOGGER.exception("Unexpected exception during reauth")
                errors["base"] = "unknown"
            else:
                if self._reauth_entry:
                    self.hass.config_entries.async_update_entry(
                        self._reauth_entry,
                        data={CONF_API_TOKEN: api_token},
                    )
                    await self.hass.config_entries.async_reload(
                        self._reauth_entry.entry_id
                    )
                    return self.async_abort(reason="reauth_successful")

        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=STEP_REAUTH_DATA_SCHEMA,
            errors=errors,
            description_placeholders={
                "title": self._reauth_entry.title if self._reauth_entry else ""
            },
        )

    async def _test_credentials(self, api_token: str) -> dict[str, Any]:
        """Validate credentials and return account info."""
        session = async_get_clientsession(self.hass)
        client = KoreWirelessAPI(session, api_token)

        # Try to fetch SIMs to validate the token
        try:
            result = await client.get_sims(page_size=1)
        except KoreWirelessAuthError:
            raise
        except KoreWirelessConnectionError:
            raise
        except Exception as err:
            _LOGGER.error("Failed to connect to Kore Wireless API: %s", err)
            raise KoreWirelessConnectionError(str(err)) from err

        # Extract account info if available
        return {
            "account_sid": result.get("meta", {}).get("account_sid"),
        }

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: ConfigEntry,
    ) -> KoreWirelessOptionsFlowHandler:
        """Get the options flow for this handler."""
        return KoreWirelessOptionsFlowHandler(config_entry)


class KoreWirelessOptionsFlowHandler(OptionsFlowWithConfigEntry):
    """Handle options flow for Kore Wireless SuperSIM."""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Manage the options."""
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Optional(
                        CONF_SCAN_INTERVAL,
                        default=self.config_entry.options.get(
                            CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL
                        ),
                    ): NumberSelector(
                        NumberSelectorConfig(
                            min=60,
                            max=3600,
                            step=60,
                            mode=NumberSelectorMode.BOX,
                            unit_of_measurement="seconds",
                        )
                    ),
                }
            ),
        )
