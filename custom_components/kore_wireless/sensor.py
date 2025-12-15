"""Sensor platform for Kore Wireless SuperSIM integration."""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import UnitOfInformation
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import KoreWirelessConfigEntry
from .const import DOMAIN
from .coordinator import KoreWirelessDataUpdateCoordinator


@dataclass(frozen=True, kw_only=True)
class KoreWirelessSensorEntityDescription(SensorEntityDescription):
    """Describes Kore Wireless sensor entity."""

    value_fn: Callable[[dict[str, Any], str], Any]
    is_account_level: bool = False


def _get_sim_status(data: dict[str, Any], sim_sid: str) -> str | None:
    """Get SIM status."""
    for sim in data.get("sims", []):
        if sim.get("sid") == sim_sid:
            return sim.get("status")
    return None


def _get_sim_iccid(data: dict[str, Any], sim_sid: str) -> str | None:
    """Get SIM ICCID."""
    for sim in data.get("sims", []):
        if sim.get("sid") == sim_sid:
            return sim.get("iccid")
    return None


def _get_sim_fleet(data: dict[str, Any], sim_sid: str) -> str | None:
    """Get SIM fleet name."""
    for sim in data.get("sims", []):
        if sim.get("sid") == sim_sid:
            fleet_sid = sim.get("fleet_sid")
            if fleet_sid:
                fleet = data.get("fleets", {}).get(fleet_sid)
                if fleet:
                    return fleet.get("unique_name") or fleet.get("sid")
            return None
    return None


def _get_sim_data_usage(data: dict[str, Any], sim_sid: str) -> float | None:
    """Get SIM data usage in MB."""
    usage = data.get("usage_by_sim", {}).get(sim_sid)
    if usage:
        bytes_used = usage.get("data_usage_bytes", 0)
        return round(bytes_used / (1024 * 1024), 2)  # Convert to MB
    return 0


def _get_sim_sms_count(data: dict[str, Any], sim_sid: str) -> int:
    """Get SIM SMS count."""
    return data.get("sms_by_sim", {}).get(sim_sid, 0)


def _get_total_sims(data: dict[str, Any], _: str) -> int:
    """Get total SIM count."""
    return data.get("account", {}).get("total_sims", 0)


def _get_active_sims(data: dict[str, Any], _: str) -> int:
    """Get active SIM count."""
    return data.get("account", {}).get("active_sims", 0)


def _get_total_data_usage(data: dict[str, Any], _: str) -> float:
    """Get total data usage in MB."""
    bytes_used = data.get("account", {}).get("total_data_usage_bytes", 0)
    return round(bytes_used / (1024 * 1024), 2)  # Convert to MB


SIM_SENSOR_DESCRIPTIONS: tuple[KoreWirelessSensorEntityDescription, ...] = (
    KoreWirelessSensorEntityDescription(
        key="status",
        translation_key="status",
        name="Status",
        icon="mdi:sim",
        value_fn=_get_sim_status,
    ),
    KoreWirelessSensorEntityDescription(
        key="iccid",
        translation_key="iccid",
        name="ICCID",
        icon="mdi:identifier",
        value_fn=_get_sim_iccid,
    ),
    KoreWirelessSensorEntityDescription(
        key="fleet",
        translation_key="fleet",
        name="Fleet",
        icon="mdi:folder-network",
        value_fn=_get_sim_fleet,
    ),
    KoreWirelessSensorEntityDescription(
        key="data_usage",
        translation_key="data_usage",
        name="Data Usage",
        icon="mdi:chart-line",
        native_unit_of_measurement=UnitOfInformation.MEGABYTES,
        device_class=SensorDeviceClass.DATA_SIZE,
        state_class=SensorStateClass.TOTAL_INCREASING,
        value_fn=_get_sim_data_usage,
    ),
    KoreWirelessSensorEntityDescription(
        key="sms_count",
        translation_key="sms_count",
        name="SMS Count",
        icon="mdi:message-text",
        state_class=SensorStateClass.TOTAL_INCREASING,
        value_fn=_get_sim_sms_count,
    ),
)

ACCOUNT_SENSOR_DESCRIPTIONS: tuple[KoreWirelessSensorEntityDescription, ...] = (
    KoreWirelessSensorEntityDescription(
        key="total_sims",
        translation_key="total_sims",
        name="Total SIMs",
        icon="mdi:sim",
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=_get_total_sims,
        is_account_level=True,
    ),
    KoreWirelessSensorEntityDescription(
        key="active_sims",
        translation_key="active_sims",
        name="Active SIMs",
        icon="mdi:sim-outline",
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=_get_active_sims,
        is_account_level=True,
    ),
    KoreWirelessSensorEntityDescription(
        key="total_data_usage",
        translation_key="total_data_usage",
        name="Total Data Usage",
        icon="mdi:chart-areaspline",
        native_unit_of_measurement=UnitOfInformation.MEGABYTES,
        device_class=SensorDeviceClass.DATA_SIZE,
        state_class=SensorStateClass.TOTAL_INCREASING,
        value_fn=_get_total_data_usage,
        is_account_level=True,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: KoreWirelessConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Kore Wireless sensors from a config entry."""
    coordinator = entry.runtime_data.coordinator

    entities: list[SensorEntity] = []

    # Add per-SIM sensors
    for sim in coordinator.data.get("sims", []):
        sim_sid = sim.get("sid")
        sim_name = sim.get("unique_name") or sim.get("iccid") or sim_sid

        for description in SIM_SENSOR_DESCRIPTIONS:
            entities.append(
                KoreWirelessSimSensor(
                    coordinator=coordinator,
                    description=description,
                    sim_sid=sim_sid,
                    sim_name=sim_name,
                )
            )

    # Add account-level sensors
    for description in ACCOUNT_SENSOR_DESCRIPTIONS:
        entities.append(
            KoreWirelessAccountSensor(
                coordinator=coordinator,
                description=description,
            )
        )

    async_add_entities(entities)


class KoreWirelessSimSensor(
    CoordinatorEntity[KoreWirelessDataUpdateCoordinator], SensorEntity
):
    """Representation of a Kore Wireless SIM sensor."""

    entity_description: KoreWirelessSensorEntityDescription
    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: KoreWirelessDataUpdateCoordinator,
        description: KoreWirelessSensorEntityDescription,
        sim_sid: str,
        sim_name: str,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self.entity_description = description
        self._sim_sid = sim_sid
        self._sim_name = sim_name
        self._attr_unique_id = f"{sim_sid}_{description.key}"

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
    def native_value(self) -> Any:
        """Return the state of the sensor."""
        return self.entity_description.value_fn(self.coordinator.data, self._sim_sid)


class KoreWirelessAccountSensor(
    CoordinatorEntity[KoreWirelessDataUpdateCoordinator], SensorEntity
):
    """Representation of a Kore Wireless account-level sensor."""

    entity_description: KoreWirelessSensorEntityDescription
    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: KoreWirelessDataUpdateCoordinator,
        description: KoreWirelessSensorEntityDescription,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self.entity_description = description
        self._attr_unique_id = f"account_{description.key}"

    @property
    def device_info(self) -> DeviceInfo:
        """Return device info."""
        return DeviceInfo(
            identifiers={(DOMAIN, "account")},
            name="Kore Wireless Account",
            manufacturer="Kore Wireless",
            model="SuperSIM Account",
        )

    @property
    def native_value(self) -> Any:
        """Return the state of the sensor."""
        return self.entity_description.value_fn(self.coordinator.data, "")
