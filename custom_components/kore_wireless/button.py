"""Button platform for Kore Wireless SuperSIM integration."""
from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.button import ButtonDeviceClass, ButtonEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import KoreWirelessConfigEntry
from .const import (
    CONF_ENABLE_BUTTONS,
    DEFAULT_ENABLE_BUTTONS,
    DOMAIN,
    SIM_STATUS_ACTIVE,
    SIM_STATUS_INACTIVE,
)
from .coordinator import KoreWirelessDataUpdateCoordinator

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: KoreWirelessConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Kore Wireless buttons from a config entry."""
    # Check if buttons are enabled
    options = entry.options
    enable_buttons = options.get(CONF_ENABLE_BUTTONS, DEFAULT_ENABLE_BUTTONS)

    if not enable_buttons:
        return

    coordinator = entry.runtime_data.coordinator
    client = entry.runtime_data.client

    entities: list[ButtonEntity] = []

    for sim in coordinator.data.get("sims", []):
        sim_sid = sim.get("sid")
        sim_name = sim.get("unique_name") or sim.get("iccid") or sim_sid

        # Add activate button
        entities.append(
            KoreWirelessActivateButton(
                coordinator=coordinator,
                client=client,
                sim_sid=sim_sid,
                sim_name=sim_name,
            )
        )

        # Add deactivate button
        entities.append(
            KoreWirelessDeactivateButton(
                coordinator=coordinator,
                client=client,
                sim_sid=sim_sid,
                sim_name=sim_name,
            )
        )

    async_add_entities(entities)


class KoreWirelessActivateButton(
    CoordinatorEntity[KoreWirelessDataUpdateCoordinator], ButtonEntity
):
    """Button to activate a Kore Wireless SIM."""

    _attr_has_entity_name = True
    _attr_name = "Activate"
    _attr_icon = "mdi:sim"

    def __init__(
        self,
        coordinator: KoreWirelessDataUpdateCoordinator,
        client: Any,
        sim_sid: str,
        sim_name: str,
    ) -> None:
        """Initialize the button."""
        super().__init__(coordinator)
        self._client = client
        self._sim_sid = sim_sid
        self._sim_name = sim_name
        self._attr_unique_id = f"{sim_sid}_activate"

    @property
    def device_info(self) -> DeviceInfo:
        """Return device info."""
        return DeviceInfo(
            identifiers={(DOMAIN, self._sim_sid)},
            name=f"SIM {self._sim_name}",
            manufacturer="Kore Wireless",
            model="SuperSIM",
        )

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        if not super().available:
            return False
        # Only available if SIM is not already active
        for sim in self.coordinator.data.get("sims", []):
            if sim.get("sid") == self._sim_sid:
                return sim.get("status") != SIM_STATUS_ACTIVE
        return False

    async def async_press(self) -> None:
        """Handle the button press."""
        _LOGGER.info("Activating SIM %s", self._sim_sid)
        try:
            await self._client.activate_sim(self._sim_sid)
            # Refresh data after status change
            await self.coordinator.async_request_refresh()
        except Exception as err:
            _LOGGER.error("Failed to activate SIM %s: %s", self._sim_sid, err)
            raise


class KoreWirelessDeactivateButton(
    CoordinatorEntity[KoreWirelessDataUpdateCoordinator], ButtonEntity
):
    """Button to deactivate a Kore Wireless SIM."""

    _attr_has_entity_name = True
    _attr_name = "Deactivate"
    _attr_icon = "mdi:sim-off"

    def __init__(
        self,
        coordinator: KoreWirelessDataUpdateCoordinator,
        client: Any,
        sim_sid: str,
        sim_name: str,
    ) -> None:
        """Initialize the button."""
        super().__init__(coordinator)
        self._client = client
        self._sim_sid = sim_sid
        self._sim_name = sim_name
        self._attr_unique_id = f"{sim_sid}_deactivate"

    @property
    def device_info(self) -> DeviceInfo:
        """Return device info."""
        return DeviceInfo(
            identifiers={(DOMAIN, self._sim_sid)},
            name=f"SIM {self._sim_name}",
            manufacturer="Kore Wireless",
            model="SuperSIM",
        )

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        if not super().available:
            return False
        # Only available if SIM is currently active
        for sim in self.coordinator.data.get("sims", []):
            if sim.get("sid") == self._sim_sid:
                return sim.get("status") == SIM_STATUS_ACTIVE
        return False

    async def async_press(self) -> None:
        """Handle the button press."""
        _LOGGER.info("Deactivating SIM %s", self._sim_sid)
        try:
            await self._client.deactivate_sim(self._sim_sid)
            # Refresh data after status change
            await self.coordinator.async_request_refresh()
        except Exception as err:
            _LOGGER.error("Failed to deactivate SIM %s: %s", self._sim_sid, err)
            raise
