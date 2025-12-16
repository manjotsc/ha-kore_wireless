"""The Kore Wireless SuperSIM integration."""
from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

import voluptuous as vol

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_SCAN_INTERVAL, Platform
from homeassistant.core import HomeAssistant, ServiceCall, ServiceResponse, SupportsResponse
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import KoreWirelessAPI, KoreWirelessAPIError
from .const import (
    ATTR_CALLBACK_URL,
    ATTR_DEVICE_ID,
    ATTR_DIRECTION,
    ATTR_MESSAGE,
    ATTR_STATUS,
    CONF_CLIENT_ID,
    CONF_CLIENT_SECRET,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
    SERVICE_GET_SMS_COMMANDS,
    SERVICE_SEND_SMS,
)
from .coordinator import KoreWirelessDataUpdateCoordinator

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [
    Platform.SENSOR,
    Platform.BINARY_SENSOR,
    Platform.BUTTON,
    Platform.DEVICE_TRACKER,
]


@dataclass
class KoreWirelessRuntimeData:
    """Runtime data for Kore Wireless integration."""

    client: KoreWirelessAPI
    coordinator: KoreWirelessDataUpdateCoordinator


type KoreWirelessConfigEntry = ConfigEntry[KoreWirelessRuntimeData]


def _get_sim_sid_from_device(hass: HomeAssistant, device_id: str) -> str:
    """Get the SIM SID from a device ID."""
    device_registry = dr.async_get(hass)
    device = device_registry.async_get(device_id)

    if device is None:
        raise ServiceValidationError(
            f"Device {device_id} not found",
            translation_domain=DOMAIN,
            translation_key="device_not_found",
        )

    # Find the SIM SID from device identifiers
    for identifier in device.identifiers:
        if identifier[0] == DOMAIN:
            return identifier[1]

    raise ServiceValidationError(
        f"Device {device_id} is not a Kore Wireless SIM device",
        translation_domain=DOMAIN,
        translation_key="invalid_device",
    )


def _get_client_for_device(hass: HomeAssistant, device_id: str) -> KoreWirelessAPI:
    """Get the API client for a device."""
    device_registry = dr.async_get(hass)
    device = device_registry.async_get(device_id)

    if device is None:
        raise ServiceValidationError(
            f"Device {device_id} not found",
            translation_domain=DOMAIN,
            translation_key="device_not_found",
        )

    # Find the config entry for this device
    for entry_id in device.config_entries:
        entry = hass.config_entries.async_get_entry(entry_id)
        if entry and entry.domain == DOMAIN:
            return entry.runtime_data.client

    raise ServiceValidationError(
        f"No Kore Wireless integration found for device {device_id}",
        translation_domain=DOMAIN,
        translation_key="integration_not_found",
    )


async def async_setup_entry(hass: HomeAssistant, entry: KoreWirelessConfigEntry) -> bool:
    """Set up Kore Wireless SuperSIM from a config entry."""
    session = async_get_clientsession(hass)
    client = KoreWirelessAPI(
        session,
        entry.data[CONF_CLIENT_ID],
        entry.data[CONF_CLIENT_SECRET],
    )

    update_interval = entry.options.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)
    coordinator = KoreWirelessDataUpdateCoordinator(
        hass, entry, client, update_interval
    )

    await coordinator.async_config_entry_first_refresh()

    entry.runtime_data = KoreWirelessRuntimeData(
        client=client,
        coordinator=coordinator,
    )

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    # Register services (only once)
    if not hass.services.has_service(DOMAIN, SERVICE_SEND_SMS):
        async def async_send_sms(call: ServiceCall) -> ServiceResponse:
            """Handle send SMS service call."""
            device_id = call.data[ATTR_DEVICE_ID]
            message = call.data[ATTR_MESSAGE]
            callback_url = call.data.get(ATTR_CALLBACK_URL)

            sim_sid = _get_sim_sid_from_device(hass, device_id)
            client = _get_client_for_device(hass, device_id)

            try:
                result = await client.send_sms_command(
                    sim=sim_sid,
                    payload=message,
                    callback_url=callback_url,
                )
                _LOGGER.info("SMS sent to SIM %s: %s", sim_sid, message[:50])
                return {
                    "success": True,
                    "sid": result.get("sid"),
                    "status": result.get("status"),
                    "date_created": result.get("date_created"),
                }
            except KoreWirelessAPIError as err:
                _LOGGER.error("Failed to send SMS to SIM %s: %s", sim_sid, err)
                raise HomeAssistantError(f"Failed to send SMS: {err}") from err

        async def async_get_sms_commands(call: ServiceCall) -> ServiceResponse:
            """Handle get SMS commands service call."""
            device_id = call.data[ATTR_DEVICE_ID]
            direction = call.data.get(ATTR_DIRECTION, "all")
            status = call.data.get(ATTR_STATUS)

            sim_sid = _get_sim_sid_from_device(hass, device_id)
            client = _get_client_for_device(hass, device_id)

            # Map direction values to API values
            api_direction = None
            if direction == "to_sim":
                api_direction = "to_sim"
            elif direction == "from_sim":
                api_direction = "from_sim"

            try:
                result = await client.get_sms_commands(
                    sim=sim_sid,
                    direction=api_direction,
                    status=status if status else None,
                )
                sms_commands = result.get("sms_commands", [])
                return {
                    "success": True,
                    "count": len(sms_commands),
                    "sms_commands": [
                        {
                            "sid": cmd.get("sid"),
                            "status": cmd.get("status"),
                            "direction": cmd.get("direction"),
                            "payload": cmd.get("payload"),
                            "date_created": cmd.get("date_created"),
                            "date_updated": cmd.get("date_updated"),
                        }
                        for cmd in sms_commands
                    ],
                }
            except KoreWirelessAPIError as err:
                _LOGGER.error("Failed to get SMS commands for SIM %s: %s", sim_sid, err)
                raise HomeAssistantError(f"Failed to get SMS commands: {err}") from err

        hass.services.async_register(
            DOMAIN,
            SERVICE_SEND_SMS,
            async_send_sms,
            supports_response=SupportsResponse.OPTIONAL,
        )

        hass.services.async_register(
            DOMAIN,
            SERVICE_GET_SMS_COMMANDS,
            async_get_sms_commands,
            supports_response=SupportsResponse.ONLY,
        )

    entry.async_on_unload(entry.add_update_listener(async_reload_entry))

    return True


async def async_unload_entry(hass: HomeAssistant, entry: KoreWirelessConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


async def async_reload_entry(hass: HomeAssistant, entry: KoreWirelessConfigEntry) -> None:
    """Reload config entry."""
    await hass.config_entries.async_reload(entry.entry_id)
