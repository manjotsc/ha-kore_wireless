"""DataUpdateCoordinator for Kore Wireless SuperSIM."""
from __future__ import annotations

from datetime import timedelta
import logging
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import KoreWirelessAPI, KoreWirelessAPIError, KoreWirelessAuthError
from .const import DOMAIN, SIM_STATUS_ACTIVE

_LOGGER = logging.getLogger(__name__)


class KoreWirelessDataUpdateCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Class to manage fetching Kore Wireless data."""

    config_entry: ConfigEntry

    def __init__(
        self,
        hass: HomeAssistant,
        config_entry: ConfigEntry,
        client: KoreWirelessAPI,
        update_interval: int,
    ) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            config_entry=config_entry,
            name=DOMAIN,
            update_interval=timedelta(seconds=update_interval),
        )
        self.client = client

    async def _async_update_data(self) -> dict[str, Any]:
        """Fetch data from Kore Wireless API."""
        try:
            # Get all SIMs
            sims = await self.client.get_all_sims()

            # Get all networks for lookup
            networks_response = await self.client.get_networks()
            networks = networks_response.get("networks", [])
            networks_by_sid = {network["sid"]: network for network in networks}

            # Initialize data structures
            usage_by_sim: dict[str, dict[str, Any]] = {}
            ip_by_sim: dict[str, list[dict[str, Any]]] = {}
            network_by_sim: dict[str, dict[str, Any]] = {}

            # Fetch data for each SIM
            for sim in sims:
                sim_sid = sim.get("sid")
                if not sim_sid:
                    continue

                # Get usage records for this SIM
                try:
                    per_sim_usage = await self.client.get_usage_records(sim=sim_sid)
                    _LOGGER.debug("Usage for SIM %s: %s", sim_sid, per_sim_usage)
                    per_sim_records = (
                        per_sim_usage.get("usage_records")
                        or per_sim_usage.get("usageRecords")
                        or []
                    )
                    if per_sim_records:
                        _LOGGER.debug("Found %d usage records for SIM %s", len(per_sim_records), sim_sid)
                        # Sum all records for this SIM
                        total_upload = sum(
                            r.get("data_upload") or r.get("dataUpload") or 0
                            for r in per_sim_records
                        )
                        total_download = sum(
                            r.get("data_download") or r.get("dataDownload") or 0
                            for r in per_sim_records
                        )
                        total_data = sum(
                            r.get("data_total") or r.get("dataTotal") or 0
                            for r in per_sim_records
                        )
                        usage_by_sim[sim_sid] = {
                            "data_upload": total_upload,
                            "data_download": total_download,
                            "data_total": total_data,
                            "data_total_billed": None,
                            "period": {},
                        }
                        _LOGGER.debug(
                            "SIM %s totals - upload: %s, download: %s, total: %s",
                            sim_sid, total_upload, total_download, total_data,
                        )
                    else:
                        _LOGGER.debug("No usage records found for SIM %s", sim_sid)
                except KoreWirelessAuthError:
                    raise
                except KoreWirelessAPIError as err:
                    _LOGGER.debug("Failed to get usage for SIM %s: %s", sim_sid, err)

                # Get usage records grouped by network to find network info
                try:
                    network_usage = await self.client.get_usage_records(
                        sim=sim_sid, group="network", granularity="all"
                    )
                    network_records = (
                        network_usage.get("usage_records")
                        or network_usage.get("usageRecords")
                        or []
                    )
                    _LOGGER.debug("Network usage for SIM %s: %s", sim_sid, network_records)

                    # Find the most recent/active network
                    if network_records:
                        # Get the record with most data usage (likely current network)
                        best_record = max(
                            network_records,
                            key=lambda r: r.get("data_total") or r.get("dataTotal") or 0
                        )
                        network_sid = best_record.get("network_sid") or best_record.get("networkSid")
                        if network_sid and network_sid in networks_by_sid:
                            network_by_sim[sim_sid] = dict(networks_by_sid[network_sid])
                            _LOGGER.debug(
                                "SIM %s network: %s",
                                sim_sid,
                                network_by_sim[sim_sid].get("friendly_name")
                            )
                except KoreWirelessAuthError:
                    raise
                except KoreWirelessAPIError as err:
                    _LOGGER.debug("Failed to get network usage for SIM %s: %s", sim_sid, err)

                # Try to get usage from billing periods if not already found
                if sim_sid not in usage_by_sim or not usage_by_sim[sim_sid].get("data_total"):
                    try:
                        billing_response = await self.client.get_sim_billing_periods(sim_sid)
                        _LOGGER.debug("Billing periods for SIM %s: %s", sim_sid, billing_response)
                        billing_periods = billing_response.get("billing_periods", [])
                        if billing_periods:
                            # Get the most recent (current) billing period
                            current_period = billing_periods[0]
                            _LOGGER.debug("Current billing period: %s", current_period)
                            usage_by_sim[sim_sid] = {
                                "data_upload": current_period.get("data_upload", 0),
                                "data_download": current_period.get("data_download", 0),
                                "data_total": current_period.get("data_total", 0),
                                "data_total_billed": current_period.get("data_total_billed"),
                                "period": {
                                    "start": current_period.get("start_time"),
                                    "end": current_period.get("end_time"),
                                },
                            }
                            _LOGGER.debug(
                                "SIM %s billing usage - upload: %s, download: %s, total: %s",
                                sim_sid,
                                usage_by_sim[sim_sid]["data_upload"],
                                usage_by_sim[sim_sid]["data_download"],
                                usage_by_sim[sim_sid]["data_total"],
                            )
                    except KoreWirelessAuthError:
                        raise
                    except KoreWirelessAPIError as err:
                        _LOGGER.debug("Failed to get billing periods for SIM %s: %s", sim_sid, err)

                # Get IP addresses
                try:
                    ip_response = await self.client.get_sim_ip_addresses(sim_sid)
                    _LOGGER.debug("IP response for SIM %s: %s", sim_sid, ip_response)
                    ip_addresses = (
                        ip_response.get("ip_addresses")
                        or ip_response.get("ipAddresses")
                        or []
                    )
                    if ip_addresses:
                        ip_by_sim[sim_sid] = ip_addresses
                        _LOGGER.debug("Found IP addresses for SIM %s: %s", sim_sid, ip_addresses)
                    else:
                        _LOGGER.debug("No IP addresses for SIM %s (no active data session)", sim_sid)
                except KoreWirelessAuthError:
                    raise
                except KoreWirelessAPIError as err:
                    _LOGGER.debug("Failed to get IP for SIM %s: %s", sim_sid, err)

            # Get fleets
            fleets_response = await self.client.get_fleets()
            fleets = fleets_response.get("fleets", [])
            fleets_by_sid = {fleet["sid"]: fleet for fleet in fleets}

            # Get SMS commands count per SIM (with direction breakdown)
            sms_by_sim: dict[str, dict[str, int]] = {}
            for sim in sims:
                sim_sid = sim.get("sid")
                if sim_sid:
                    try:
                        sms = await self.client.get_sms_commands(sim=sim_sid)
                        sms_commands = sms.get("sms_commands") or sms.get("smsCommands") or []

                        # Count by direction
                        sent = 0  # to_sim (sent TO the device)
                        received = 0  # from_sim (received FROM the device)
                        for cmd in sms_commands:
                            direction = cmd.get("direction")
                            if direction == "to_sim":
                                sent += 1
                            elif direction == "from_sim":
                                received += 1

                        sms_by_sim[sim_sid] = {
                            "sent": sent,
                            "received": received,
                            "total": len(sms_commands),
                        }
                    except KoreWirelessAuthError:
                        raise
                    except KoreWirelessAPIError:
                        sms_by_sim[sim_sid] = {"sent": 0, "received": 0, "total": 0}

            # Calculate account-level stats
            total_sims = len(sims)
            active_sims = sum(
                1 for sim in sims if sim.get("status") == SIM_STATUS_ACTIVE
            )

            # Sum up usage across all SIMs
            total_upload = sum(
                usage.get("data_upload", 0) for usage in usage_by_sim.values()
            )
            total_download = sum(
                usage.get("data_download", 0) for usage in usage_by_sim.values()
            )
            total_data = sum(
                usage.get("data_total", 0) for usage in usage_by_sim.values()
            )

            # Sum up SMS across all SIMs
            total_sms_sent = sum(
                sms.get("sent", 0) for sms in sms_by_sim.values()
            )
            total_sms_received = sum(
                sms.get("received", 0) for sms in sms_by_sim.values()
            )
            total_sms = sum(
                sms.get("total", 0) for sms in sms_by_sim.values()
            )

            return {
                "sims": sims,
                "usage_by_sim": usage_by_sim,
                "sms_by_sim": sms_by_sim,
                "ip_by_sim": ip_by_sim,
                "network_by_sim": network_by_sim,
                "networks": networks_by_sid,
                "fleets": fleets_by_sid,
                "account": {
                    "total_sims": total_sims,
                    "active_sims": active_sims,
                    "data_upload": total_upload,
                    "data_download": total_download,
                    "data_total": total_data,
                    "sms_sent": total_sms_sent,
                    "sms_received": total_sms_received,
                    "sms_total": total_sms,
                },
            }

        except KoreWirelessAuthError as err:
            raise ConfigEntryAuthFailed(
                "API credentials are invalid or expired"
            ) from err
        except KoreWirelessAPIError as err:
            raise UpdateFailed(
                f"Error communicating with Kore Wireless API: {err}"
            ) from err
