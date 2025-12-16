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
from .const import CONF_ENABLE_ACCOUNT_SENSORS, DEFAULT_ENABLE_ACCOUNT_SENSORS, DOMAIN
from .coordinator import KoreWirelessDataUpdateCoordinator

# Default enabled sensors
DEFAULT_SIM_SENSORS = [
    "status",
    "iccid",
    "fleet",
    "data_download",
    "data_upload",
    "data_total",
    "sms_received",
    "sms_sent",
    "sms_total",
    "network_operator",
    "network_country",
    "ip_address",
]


def _bytes_to_mb(value: int | float | None) -> float:
    """Convert bytes to megabytes."""
    if value is None:
        return 0.0
    return round(value / (1024 * 1024), 3)


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


def _get_sim_data_upload(data: dict[str, Any], sim_sid: str) -> float:
    """Get SIM data upload in MB."""
    usage = data.get("usage_by_sim", {}).get(sim_sid, {})
    return _bytes_to_mb(usage.get("data_upload", 0))


def _get_sim_data_download(data: dict[str, Any], sim_sid: str) -> float:
    """Get SIM data download in MB."""
    usage = data.get("usage_by_sim", {}).get(sim_sid, {})
    return _bytes_to_mb(usage.get("data_download", 0))


def _get_sim_data_total(data: dict[str, Any], sim_sid: str) -> float:
    """Get SIM total data usage in MB."""
    usage = data.get("usage_by_sim", {}).get(sim_sid, {})
    return _bytes_to_mb(usage.get("data_total", 0))


def _get_sim_sms_received(data: dict[str, Any], sim_sid: str) -> int:
    """Get SIM SMS received count."""
    return data.get("sms_by_sim", {}).get(sim_sid, {}).get("received", 0)


def _get_sim_sms_sent(data: dict[str, Any], sim_sid: str) -> int:
    """Get SIM SMS sent count."""
    return data.get("sms_by_sim", {}).get(sim_sid, {}).get("sent", 0)


def _get_sim_sms_total(data: dict[str, Any], sim_sid: str) -> int:
    """Get SIM SMS total count."""
    return data.get("sms_by_sim", {}).get(sim_sid, {}).get("total", 0)


def _get_sim_network_operator(data: dict[str, Any], sim_sid: str) -> str | None:
    """Get SIM network operator name."""
    network = data.get("network_by_sim", {}).get(sim_sid, {})
    friendly_name = network.get("friendly_name")
    if friendly_name:
        return friendly_name
    # Return None if no network data (requires usage records)
    return None


def _get_sim_network_country(data: dict[str, Any], sim_sid: str) -> str | None:
    """Get SIM network country."""
    network = data.get("network_by_sim", {}).get(sim_sid, {})
    iso_country = network.get("iso_country")
    if iso_country:
        return iso_country.upper()
    return None


def _get_sim_ip_address(data: dict[str, Any], sim_sid: str) -> str:
    """Get SIM IP address."""
    ip_addresses = data.get("ip_by_sim", {}).get(sim_sid, [])
    if ip_addresses:
        first_ip = ip_addresses[0]
        ip = first_ip.get("ip_address") or first_ip.get("ipAddress")
        if ip:
            return ip
    # IP only available for VPN-enabled fleets
    return "VPN required"


def _get_total_sims(data: dict[str, Any], _: str) -> int:
    """Get total SIM count."""
    return data.get("account", {}).get("total_sims", 0)


def _get_active_sims(data: dict[str, Any], _: str) -> int:
    """Get active SIM count."""
    return data.get("account", {}).get("active_sims", 0)


def _get_account_data_upload(data: dict[str, Any], _: str) -> float:
    """Get account total data upload in MB."""
    return _bytes_to_mb(data.get("account", {}).get("data_upload", 0))


def _get_account_data_download(data: dict[str, Any], _: str) -> float:
    """Get account total data download in MB."""
    return _bytes_to_mb(data.get("account", {}).get("data_download", 0))


def _get_account_data_total(data: dict[str, Any], _: str) -> float:
    """Get account total data usage in MB."""
    return _bytes_to_mb(data.get("account", {}).get("data_total", 0))


def _get_account_sms_received(data: dict[str, Any], _: str) -> int:
    """Get account total SMS received count."""
    return data.get("account", {}).get("sms_received", 0)


def _get_account_sms_sent(data: dict[str, Any], _: str) -> int:
    """Get account total SMS sent count."""
    return data.get("account", {}).get("sms_sent", 0)


def _get_account_sms_total(data: dict[str, Any], _: str) -> int:
    """Get account total SMS count."""
    return data.get("account", {}).get("sms_total", 0)


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
        key="data_download",
        translation_key="data_download",
        name="Data Download",
        icon="mdi:download",
        native_unit_of_measurement=UnitOfInformation.MEGABYTES,
        device_class=SensorDeviceClass.DATA_SIZE,
        state_class=SensorStateClass.TOTAL_INCREASING,
        suggested_display_precision=3,
        value_fn=_get_sim_data_download,
    ),
    KoreWirelessSensorEntityDescription(
        key="data_upload",
        translation_key="data_upload",
        name="Data Upload",
        icon="mdi:upload",
        native_unit_of_measurement=UnitOfInformation.MEGABYTES,
        device_class=SensorDeviceClass.DATA_SIZE,
        state_class=SensorStateClass.TOTAL_INCREASING,
        suggested_display_precision=3,
        value_fn=_get_sim_data_upload,
    ),
    KoreWirelessSensorEntityDescription(
        key="data_total",
        translation_key="data_total",
        name="Data Total",
        icon="mdi:chart-line",
        native_unit_of_measurement=UnitOfInformation.MEGABYTES,
        device_class=SensorDeviceClass.DATA_SIZE,
        state_class=SensorStateClass.TOTAL_INCREASING,
        suggested_display_precision=3,
        value_fn=_get_sim_data_total,
    ),
    KoreWirelessSensorEntityDescription(
        key="sms_received",
        translation_key="sms_received",
        name="SMS Received",
        icon="mdi:message-arrow-left",
        state_class=SensorStateClass.TOTAL_INCREASING,
        value_fn=_get_sim_sms_received,
    ),
    KoreWirelessSensorEntityDescription(
        key="sms_sent",
        translation_key="sms_sent",
        name="SMS Sent",
        icon="mdi:message-arrow-right",
        state_class=SensorStateClass.TOTAL_INCREASING,
        value_fn=_get_sim_sms_sent,
    ),
    KoreWirelessSensorEntityDescription(
        key="sms_total",
        translation_key="sms_total",
        name="SMS Total",
        icon="mdi:message-text",
        state_class=SensorStateClass.TOTAL_INCREASING,
        value_fn=_get_sim_sms_total,
    ),
    KoreWirelessSensorEntityDescription(
        key="network_operator",
        translation_key="network_operator",
        name="Network Operator",
        icon="mdi:antenna",
        value_fn=_get_sim_network_operator,
    ),
    KoreWirelessSensorEntityDescription(
        key="network_country",
        translation_key="network_country",
        name="Network Country",
        icon="mdi:earth",
        value_fn=_get_sim_network_country,
    ),
    KoreWirelessSensorEntityDescription(
        key="ip_address",
        translation_key="ip_address",
        name="IP Address",
        icon="mdi:ip-network",
        value_fn=_get_sim_ip_address,
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
        key="account_data_upload",
        translation_key="account_data_upload",
        name="Total Data Upload",
        icon="mdi:upload",
        native_unit_of_measurement=UnitOfInformation.MEGABYTES,
        device_class=SensorDeviceClass.DATA_SIZE,
        state_class=SensorStateClass.TOTAL_INCREASING,
        suggested_display_precision=3,
        value_fn=_get_account_data_upload,
        is_account_level=True,
    ),
    KoreWirelessSensorEntityDescription(
        key="account_data_download",
        translation_key="account_data_download",
        name="Total Data Download",
        icon="mdi:download",
        native_unit_of_measurement=UnitOfInformation.MEGABYTES,
        device_class=SensorDeviceClass.DATA_SIZE,
        state_class=SensorStateClass.TOTAL_INCREASING,
        suggested_display_precision=3,
        value_fn=_get_account_data_download,
        is_account_level=True,
    ),
    KoreWirelessSensorEntityDescription(
        key="account_data_total",
        translation_key="account_data_total",
        name="Total Data Usage",
        icon="mdi:chart-areaspline",
        native_unit_of_measurement=UnitOfInformation.MEGABYTES,
        device_class=SensorDeviceClass.DATA_SIZE,
        state_class=SensorStateClass.TOTAL_INCREASING,
        suggested_display_precision=3,
        value_fn=_get_account_data_total,
        is_account_level=True,
    ),
    KoreWirelessSensorEntityDescription(
        key="account_sms_received",
        translation_key="account_sms_received",
        name="Total SMS Received",
        icon="mdi:message-arrow-left",
        state_class=SensorStateClass.TOTAL_INCREASING,
        value_fn=_get_account_sms_received,
        is_account_level=True,
    ),
    KoreWirelessSensorEntityDescription(
        key="account_sms_sent",
        translation_key="account_sms_sent",
        name="Total SMS Sent",
        icon="mdi:message-arrow-right",
        state_class=SensorStateClass.TOTAL_INCREASING,
        value_fn=_get_account_sms_sent,
        is_account_level=True,
    ),
    KoreWirelessSensorEntityDescription(
        key="account_sms_total",
        translation_key="account_sms_total",
        name="Total SMS",
        icon="mdi:message-text",
        state_class=SensorStateClass.TOTAL_INCREASING,
        value_fn=_get_account_sms_total,
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

    # Get options
    options = entry.options
    enabled_sim_sensors = options.get("sim_sensors", DEFAULT_SIM_SENSORS)
    enable_account_sensors = options.get(
        CONF_ENABLE_ACCOUNT_SENSORS, DEFAULT_ENABLE_ACCOUNT_SENSORS
    )

    entities: list[SensorEntity] = []

    # Add per-SIM sensors (only enabled ones)
    for sim in coordinator.data.get("sims", []):
        sim_sid = sim.get("sid")
        sim_name = sim.get("unique_name") or sim.get("iccid") or sim_sid

        for description in SIM_SENSOR_DESCRIPTIONS:
            # Check if this sensor type is enabled
            if description.key in enabled_sim_sensors:
                entities.append(
                    KoreWirelessSimSensor(
                        coordinator=coordinator,
                        description=description,
                        sim_sid=sim_sid,
                        sim_name=sim_name,
                    )
                )

    # Add account-level sensors (if enabled)
    if enable_account_sensors:
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
