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
    CONF_CLIENT_ID,
    CONF_CLIENT_SECRET,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_CLIENT_ID): TextSelector(
            TextSelectorConfig(type=TextSelectorType.TEXT)
        ),
        vol.Required(CONF_CLIENT_SECRET): TextSelector(
            TextSelectorConfig(type=TextSelectorType.PASSWORD)
        ),
    }
)

STEP_REAUTH_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_CLIENT_ID): TextSelector(
            TextSelectorConfig(type=TextSelectorType.TEXT)
        ),
        vol.Required(CONF_CLIENT_SECRET): TextSelector(
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
            client_id = user_input[CONF_CLIENT_ID]
            client_secret = user_input[CONF_CLIENT_SECRET]

            try:
                account_info = await self._test_credentials(client_id, client_secret)
            except KoreWirelessAuthError:
                errors["base"] = "invalid_auth"
            except KoreWirelessConnectionError:
                errors["base"] = "cannot_connect"
            except Exception:
                _LOGGER.exception("Unexpected exception during setup")
                errors["base"] = "unknown"
            else:
                # Use client_id as unique ID
                await self.async_set_unique_id(client_id)
                self._abort_if_unique_id_configured()

                return self.async_create_entry(
                    title="Kore Wireless SuperSIM",
                    data={
                        CONF_CLIENT_ID: client_id,
                        CONF_CLIENT_SECRET: client_secret,
                    },
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
            client_id = user_input[CONF_CLIENT_ID]
            client_secret = user_input[CONF_CLIENT_SECRET]

            try:
                await self._test_credentials(client_id, client_secret)
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
                        data={
                            CONF_CLIENT_ID: client_id,
                            CONF_CLIENT_SECRET: client_secret,
                        },
                    )
                    await self.hass.config_entries.async_reload(
                        self._reauth_entry.entry_id
                    )
                    return self.async_abort(reason="reauth_successful")

        # Pre-fill client_id if available
        suggested_values = {}
        if self._reauth_entry:
            suggested_values[CONF_CLIENT_ID] = self._reauth_entry.data.get(CONF_CLIENT_ID, "")

        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=self.add_suggested_values_to_schema(
                STEP_REAUTH_DATA_SCHEMA, suggested_values
            ),
            errors=errors,
            description_placeholders={
                "title": self._reauth_entry.title if self._reauth_entry else ""
            },
        )

    async def _test_credentials(
        self, client_id: str, client_secret: str
    ) -> dict[str, Any]:
        """Validate credentials and return account info."""
        session = async_get_clientsession(self.hass)
        client = KoreWirelessAPI(session, client_id, client_secret)

        # Try to fetch SIMs to validate the credentials
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
