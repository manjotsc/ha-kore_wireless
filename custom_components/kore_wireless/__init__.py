"""The Kore Wireless SuperSIM integration."""
from __future__ import annotations

import logging
from dataclasses import dataclass

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_SCAN_INTERVAL, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import KoreWirelessAPI
from .const import (
    CONF_API_TOKEN,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
)
from .coordinator import KoreWirelessDataUpdateCoordinator

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [
    Platform.SENSOR,
    Platform.BINARY_SENSOR,
    Platform.DEVICE_TRACKER,
]


@dataclass
class KoreWirelessRuntimeData:
    """Runtime data for Kore Wireless integration."""

    client: KoreWirelessAPI
    coordinator: KoreWirelessDataUpdateCoordinator


type KoreWirelessConfigEntry = ConfigEntry[KoreWirelessRuntimeData]


async def async_setup_entry(hass: HomeAssistant, entry: KoreWirelessConfigEntry) -> bool:
    """Set up Kore Wireless SuperSIM from a config entry."""
    session = async_get_clientsession(hass)
    client = KoreWirelessAPI(session, entry.data[CONF_API_TOKEN])

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

    entry.async_on_unload(entry.add_update_listener(async_reload_entry))

    return True


async def async_unload_entry(hass: HomeAssistant, entry: KoreWirelessConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


async def async_reload_entry(hass: HomeAssistant, entry: KoreWirelessConfigEntry) -> None:
    """Reload config entry."""
    await hass.config_entries.async_reload(entry.entry_id)
