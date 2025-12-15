"""Device tracker platform for Kore Wireless SuperSIM integration."""
from __future__ import annotations

from typing import Any

from homeassistant.components.device_tracker import SourceType
from homeassistant.components.device_tracker.config_entry import TrackerEntity
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
    """Set up Kore Wireless device trackers from a config entry."""
    coordinator = entry.runtime_data.coordinator

    entities: list[TrackerEntity] = []

    for sim in coordinator.data.get("sims", []):
        sim_sid = sim.get("sid")
        sim_name = sim.get("unique_name") or sim.get("iccid") or sim_sid

        entities.append(
            KoreWirelessSimTracker(
                coordinator=coordinator,
                sim_sid=sim_sid,
                sim_name=sim_name,
            )
        )

    async_add_entities(entities)


class KoreWirelessSimTracker(
    CoordinatorEntity[KoreWirelessDataUpdateCoordinator], TrackerEntity
):
    """Representation of a Kore Wireless SIM device tracker."""

    _attr_has_entity_name = True
    _attr_name = "Location"

    def __init__(
        self,
        coordinator: KoreWirelessDataUpdateCoordinator,
        sim_sid: str,
        sim_name: str,
    ) -> None:
        """Initialize the device tracker."""
        super().__init__(coordinator)
        self._sim_sid = sim_sid
        self._sim_name = sim_name
        self._attr_unique_id = f"{sim_sid}_location"

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
    def source_type(self) -> SourceType:
        """Return the source type of the device tracker."""
        return SourceType.GPS

    @property
    def latitude(self) -> float | None:
        """Return latitude value of the device."""
        for sim in self.coordinator.data.get("sims", []):
            if sim.get("sid") == self._sim_sid:
                if "latitude" in sim:
                    return sim.get("latitude")
                usage = self.coordinator.data.get("usage_by_sim", {}).get(self._sim_sid, {})
                records = usage.get("records", [])
                if records:
                    for record in reversed(records):
                        if "latitude" in record:
                            return record.get("latitude")
        return None

    @property
    def longitude(self) -> float | None:
        """Return longitude value of the device."""
        for sim in self.coordinator.data.get("sims", []):
            if sim.get("sid") == self._sim_sid:
                if "longitude" in sim:
                    return sim.get("longitude")
                usage = self.coordinator.data.get("usage_by_sim", {}).get(self._sim_sid, {})
                records = usage.get("records", [])
                if records:
                    for record in reversed(records):
                        if "longitude" in record:
                            return record.get("longitude")
        return None

    @property
    def location_name(self) -> str | None:
        """Return a location name for the current location of the device."""
        for sim in self.coordinator.data.get("sims", []):
            if sim.get("sid") == self._sim_sid:
                usage = self.coordinator.data.get("usage_by_sim", {}).get(self._sim_sid, {})
                records = usage.get("records", [])
                if records:
                    latest = records[-1]
                    network = latest.get("network", {})
                    if isinstance(network, dict):
                        return network.get("friendly_name")
        return None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return extra state attributes."""
        attributes: dict[str, Any] = {}

        for sim in self.coordinator.data.get("sims", []):
            if sim.get("sid") == self._sim_sid:
                attributes["sim_sid"] = sim.get("sid")
                attributes["iccid"] = sim.get("iccid")
                attributes["status"] = sim.get("status")
                attributes["is_active"] = sim.get("status") == SIM_STATUS_ACTIVE

                usage = self.coordinator.data.get("usage_by_sim", {}).get(self._sim_sid, {})
                records = usage.get("records", [])
                if records:
                    latest = records[-1]
                    network = latest.get("network", {})
                    if isinstance(network, dict):
                        attributes["network_name"] = network.get("friendly_name")
                        attributes["network_iso_country"] = network.get("iso_country")
                        attributes["network_mcc"] = network.get("mcc")
                        attributes["network_mnc"] = network.get("mnc")

                break

        return attributes
