"""Config flow for Kore Wireless SuperSIM integration."""
from __future__ import annotations

import csv
import io
import logging
from typing import Any

import voluptuous as vol

from homeassistant.components.file_upload import process_uploaded_file
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
    BooleanSelector,
    FileSelector,
    FileSelectorConfig,
    NumberSelector,
    NumberSelectorConfig,
    NumberSelectorMode,
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
    TextSelector,
    TextSelectorConfig,
    TextSelectorType,
)

from .api import KoreWirelessAPI, KoreWirelessAuthError, KoreWirelessConnectionError
from .const import (
    CONF_CLIENT_ID,
    CONF_CLIENT_SECRET,
    CONF_ENABLE_BUTTONS,
    CONF_ENABLE_ACCOUNT_SENSORS,
    CONF_SENSOR_DATA_DOWNLOAD,
    CONF_SENSOR_DATA_TOTAL,
    CONF_SENSOR_DATA_UPLOAD,
    CONF_SENSOR_FLEET,
    CONF_SENSOR_ICCID,
    CONF_SENSOR_IP_ADDRESS,
    CONF_SENSOR_NETWORK_COUNTRY,
    CONF_SENSOR_NETWORK_OPERATOR,
    CONF_SENSOR_SMS_COUNT,
    CONF_SENSOR_STATUS,
    DEFAULT_ENABLE_BUTTONS,
    DEFAULT_ENABLE_ACCOUNT_SENSORS,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)

CONF_CREDENTIALS_FILE = "credentials_file"

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
        """Handle the initial step - show menu to choose setup method."""
        return self.async_show_menu(
            step_id="user",
            menu_options={
                "manual": "Enter credentials manually",
                "csv_upload": "Upload credentials CSV file",
            },
        )

    async def async_step_manual(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle manual credential entry."""
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
            step_id="manual",
            data_schema=STEP_USER_DATA_SCHEMA,
            errors=errors,
        )

    async def async_step_csv_upload(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle CSV file upload for credentials."""
        errors: dict[str, str] = {}

        if user_input is not None:
            file_id = user_input.get(CONF_CREDENTIALS_FILE)

            if file_id:
                try:
                    # Read the uploaded file
                    uploaded_file = await self.hass.async_add_executor_job(
                        self._read_uploaded_file, file_id
                    )

                    # Parse CSV content
                    credentials = self._parse_kore_csv(uploaded_file)

                    if not credentials.get("client_id") or not credentials.get("client_secret"):
                        errors["base"] = "invalid_csv"
                    else:
                        client_id = credentials["client_id"]
                        client_secret = credentials["client_secret"]

                        try:
                            await self._test_credentials(client_id, client_secret)
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

                            title = credentials.get("client_name", "Kore Wireless SuperSIM")

                            return self.async_create_entry(
                                title=title,
                                data={
                                    CONF_CLIENT_ID: client_id,
                                    CONF_CLIENT_SECRET: client_secret,
                                },
                                options={CONF_SCAN_INTERVAL: DEFAULT_SCAN_INTERVAL},
                            )
                except Exception as err:
                    _LOGGER.exception("Failed to parse CSV file: %s", err)
                    errors["base"] = "invalid_csv"

        return self.async_show_form(
            step_id="csv_upload",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_CREDENTIALS_FILE): FileSelector(
                        FileSelectorConfig(accept=".csv")
                    ),
                }
            ),
            errors=errors,
        )

    def _read_uploaded_file(self, file_id: str) -> str:
        """Read content from uploaded file."""
        with process_uploaded_file(self.hass, file_id) as file_path:
            return file_path.read_text(encoding="utf-8")

    def _parse_kore_csv(self, content: str) -> dict[str, str]:
        """Parse Kore Wireless credentials CSV file.

        Expected format:
        Client Details,Value
        client_name,<name>
        client_id,<id>
        client_secret,<secret>
        date_updated,<date>
        """
        credentials: dict[str, str] = {}

        reader = csv.reader(io.StringIO(content))

        for row in reader:
            if len(row) >= 2:
                key = row[0].strip().lower()
                value = row[1].strip()

                if key == "client_id":
                    credentials["client_id"] = value
                elif key == "client_secret":
                    credentials["client_secret"] = value
                elif key == "client_name":
                    credentials["client_name"] = value

        return credentials

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

        # Get current options with defaults
        options = self.config_entry.options

        # Define available SIM sensor options
        sim_sensor_options = [
            {"value": "status", "label": "Status"},
            {"value": "iccid", "label": "ICCID"},
            {"value": "fleet", "label": "Fleet"},
            {"value": "data_download", "label": "Data Download"},
            {"value": "data_upload", "label": "Data Upload"},
            {"value": "data_total", "label": "Data Total"},
            {"value": "sms_received", "label": "SMS Received"},
            {"value": "sms_sent", "label": "SMS Sent"},
            {"value": "sms_total", "label": "SMS Total"},
            {"value": "network_operator", "label": "Network Operator"},
            {"value": "network_country", "label": "Network Country"},
            {"value": "ip_address", "label": "IP Address"},
        ]

        # Default all sensors enabled
        default_sim_sensors = [opt["value"] for opt in sim_sensor_options]

        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Optional(
                        CONF_SCAN_INTERVAL,
                        default=options.get(
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
                    vol.Optional(
                        CONF_ENABLE_BUTTONS,
                        default=options.get(
                            CONF_ENABLE_BUTTONS, DEFAULT_ENABLE_BUTTONS
                        ),
                    ): BooleanSelector(),
                    vol.Optional(
                        CONF_ENABLE_ACCOUNT_SENSORS,
                        default=options.get(
                            CONF_ENABLE_ACCOUNT_SENSORS, DEFAULT_ENABLE_ACCOUNT_SENSORS
                        ),
                    ): BooleanSelector(),
                    vol.Optional(
                        "sim_sensors",
                        default=options.get("sim_sensors", default_sim_sensors),
                    ): SelectSelector(
                        SelectSelectorConfig(
                            options=sim_sensor_options,
                            multiple=True,
                            mode=SelectSelectorMode.DROPDOWN,
                        )
                    ),
                }
            ),
        )
