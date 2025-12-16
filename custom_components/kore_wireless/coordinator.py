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

            # Get usage records grouped by SIM to get totals
            try:
                sim_usage_response = await self.client.get_usage_records(
                    granularity="all",
                    group="sim",
                )
                usage_records = sim_usage_response.get("usage_records", [])
                for record in usage_records:
                    sim_sid = record.get("sim_sid")
                    if sim_sid:
                        usage_by_sim[sim_sid] = {
                            "data_upload": record.get("data_upload", 0),
                            "data_download": record.get("data_download", 0),
                            "data_total": record.get("data_total", 0),
                            "data_total_billed": record.get("data_total_billed"),
                            "period": record.get("period", {}),
                        }
            except KoreWirelessAuthError:
                raise
            except KoreWirelessAPIError as err:
                _LOGGER.debug("Failed to get grouped usage records: %s", err)

            # Get usage records grouped by network to find which network each SIM uses
            try:
                network_usage_response = await self.client.get_usage_records(
                    granularity="all",
                    group="network",
                )
                network_records = network_usage_response.get("usage_records", [])
                # Build a map of network usage
                for record in network_records:
                    network_sid = record.get("network_sid")
                    if network_sid and network_sid in networks_by_sid:
                        _LOGGER.debug("Found network usage for: %s", network_sid)
            except KoreWirelessAuthError:
                raise
            except KoreWirelessAPIError as err:
                _LOGGER.debug("Failed to get network usage records: %s", err)

            # For each SIM, get per-SIM usage with network info
            for sim in sims:
                sim_sid = sim.get("sid")
                if not sim_sid:
                    continue

                # Get usage for this specific SIM grouped by network to find connected network
                try:
                    sim_network_usage = await self.client.get_usage_records(
                        sim=sim_sid,
                        granularity="all",
                        group="network",
                    )
                    sim_network_records = sim_network_usage.get("usage_records", [])
                    if sim_network_records:
                        # Get the network with the most recent/most usage
                        latest_record = sim_network_records[-1]
                        network_sid = latest_record.get("network_sid")
                        if network_sid and network_sid in networks_by_sid:
                            network_by_sim[sim_sid] = networks_by_sid[network_sid]
                        # Also get iso_country from the record
                        iso_country = latest_record.get("iso_country")
                        if iso_country and sim_sid not in network_by_sim:
                            network_by_sim[sim_sid] = {"iso_country": iso_country}
                        elif iso_country and sim_sid in network_by_sim:
                            network_by_sim[sim_sid]["iso_country"] = iso_country
                except KoreWirelessAuthError:
                    raise
                except KoreWirelessAPIError as err:
                    _LOGGER.debug("Failed to get network for SIM %s: %s", sim_sid, err)

                # Get IP addresses
                try:
                    ip_response = await self.client.get_sim_ip_addresses(sim_sid)
                    ip_addresses = ip_response.get("ip_addresses", [])
                    if ip_addresses:
                        ip_by_sim[sim_sid] = ip_addresses
                except KoreWirelessAuthError:
                    raise
                except KoreWirelessAPIError as err:
                    _LOGGER.debug("Failed to get IP for SIM %s: %s", sim_sid, err)

            # Get fleets
            fleets_response = await self.client.get_fleets()
            fleets = fleets_response.get("fleets", [])
            fleets_by_sid = {fleet["sid"]: fleet for fleet in fleets}

            # Get SMS commands count per SIM
            sms_by_sim: dict[str, int] = {}
            for sim in sims:
                sim_sid = sim.get("sid")
                if sim_sid:
                    try:
                        sms = await self.client.get_sms_commands(sim=sim_sid)
                        sms_by_sim[sim_sid] = len(sms.get("sms_commands", []))
                    except KoreWirelessAuthError:
                        raise
                    except KoreWirelessAPIError:
                        sms_by_sim[sim_sid] = 0

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
