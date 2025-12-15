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

            # Get usage records for each SIM
            usage_by_sim: dict[str, dict[str, Any]] = {}
            for sim in sims:
                sim_sid = sim.get("sid")
                if sim_sid:
                    try:
                        usage = await self.client.get_usage_records(sim=sim_sid)
                        usage_records = usage.get("usage_records", [])
                        if usage_records:
                            # Sum up data usage
                            total_data = sum(
                                record.get("data_upload", 0) + record.get("data_download", 0)
                                for record in usage_records
                            )
                            usage_by_sim[sim_sid] = {
                                "data_usage_bytes": total_data,
                                "records": usage_records,
                            }
                    except KoreWirelessAuthError:
                        # Re-raise auth errors to trigger reauth
                        raise
                    except KoreWirelessAPIError as err:
                        _LOGGER.debug("Failed to get usage for SIM %s: %s", sim_sid, err)

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
                        # Re-raise auth errors to trigger reauth
                        raise
                    except KoreWirelessAPIError:
                        sms_by_sim[sim_sid] = 0

            # Calculate account-level stats
            total_sims = len(sims)
            active_sims = sum(
                1 for sim in sims if sim.get("status") == SIM_STATUS_ACTIVE
            )
            total_data_usage = sum(
                usage.get("data_usage_bytes", 0) for usage in usage_by_sim.values()
            )

            return {
                "sims": sims,
                "usage_by_sim": usage_by_sim,
                "sms_by_sim": sms_by_sim,
                "fleets": fleets_by_sid,
                "account": {
                    "total_sims": total_sims,
                    "active_sims": active_sims,
                    "total_data_usage_bytes": total_data_usage,
                },
            }

        except KoreWirelessAuthError as err:
            # Trigger reauth flow when authentication fails
            raise ConfigEntryAuthFailed(
                "API token is invalid or expired"
            ) from err
        except KoreWirelessAPIError as err:
            raise UpdateFailed(
                f"Error communicating with Kore Wireless API: {err}"
            ) from err
