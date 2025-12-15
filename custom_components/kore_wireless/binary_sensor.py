"""Binary sensor platform for Kore Wireless SuperSIM integration."""
from __future__ import annotations

from typing import Any

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import KoreWirelessConfigEntry
from .const import DOMAIN, SIM_STATUS_ACTIVE
from .coordinator import KoreWirelessDataUpdateCoordinator


async def async_setup_entry(
    hass: HomeAssistant,
    entry: KoreWirelessConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Kore Wireless binary sensors from a config entry."""
    coordinator = entry.runtime_data.coordinator

    entities: list[BinarySensorEntity] = []

    for sim in coordinator.data.get("sims", []):
        sim_sid = sim.get("sid")
        sim_name = sim.get("unique_name") or sim.get("iccid") or sim_sid

        entities.append(
            KoreWirelessSimActiveBinarySensor(
                coordinator=coordinator,
                sim_sid=sim_sid,
                sim_name=sim_name,
            )
        )

    async_add_entities(entities)


class KoreWirelessSimActiveBinarySensor(
    CoordinatorEntity[KoreWirelessDataUpdateCoordinator], BinarySensorEntity
):
    """Representation of a Kore Wireless SIM active binary sensor."""

    _attr_has_entity_name = True
    _attr_device_class = BinarySensorDeviceClass.CONNECTIVITY
    _attr_name = "Active"

    def __init__(
        self,
        coordinator: KoreWirelessDataUpdateCoordinator,
        sim_sid: str,
        sim_name: str,
    ) -> None:
        """Initialize the binary sensor."""
        super().__init__(coordinator)
        self._sim_sid = sim_sid
        self._sim_name = sim_name
        self._attr_unique_id = f"{sim_sid}_active"

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
    def is_on(self) -> bool:
        """Return true if the SIM is active."""
        for sim in self.coordinator.data.get("sims", []):
            if sim.get("sid") == self._sim_sid:
                return sim.get("status") == SIM_STATUS_ACTIVE
        return False

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return extra state attributes."""
        for sim in self.coordinator.data.get("sims", []):
            if sim.get("sid") == self._sim_sid:
                return {
                    "status": sim.get("status"),
                    "sid": sim.get("sid"),
                    "iccid": sim.get("iccid"),
                    "fleet_sid": sim.get("fleet_sid"),
                    "unique_name": sim.get("unique_name"),
                    "date_created": sim.get("date_created"),
                    "date_updated": sim.get("date_updated"),
                }
        return {}
