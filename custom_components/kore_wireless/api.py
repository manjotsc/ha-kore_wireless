"""Kore Wireless SuperSIM API client."""
from __future__ import annotations

import logging
from typing import Any

import aiohttp
from aiohttp import ClientError, ClientResponseError

from .const import API_BASE_URL

_LOGGER = logging.getLogger(__name__)


class KoreWirelessAPIError(Exception):
    """Base exception for Kore Wireless API errors."""


class KoreWirelessAuthError(KoreWirelessAPIError):
    """Authentication error."""


class KoreWirelessConnectionError(KoreWirelessAPIError):
    """Connection error."""


class KoreWirelessAPI:
    """Kore Wireless SuperSIM API client."""

    def __init__(self, session: aiohttp.ClientSession, api_token: str) -> None:
        """Initialize the API client."""
        self._session = session
        self._api_token = api_token
        self._headers = {
            "Authorization": f"Bearer {api_token}",
            "Content-Type": "application/json",
        }

    async def _request(
        self,
        method: str,
        endpoint: str,
        params: dict[str, Any] | None = None,
        data: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Make an API request."""
        url = f"{API_BASE_URL}/{endpoint}"

        try:
            async with self._session.request(
                method,
                url,
                headers=self._headers,
                params=params,
                json=data,
            ) as response:
                if response.status == 401:
                    raise KoreWirelessAuthError("Invalid API token")
                if response.status == 403:
                    raise KoreWirelessAuthError("Access forbidden")

                response.raise_for_status()
                return await response.json()

        except ClientResponseError as err:
            _LOGGER.error("API request failed: %s", err)
            raise KoreWirelessAPIError(f"API request failed: {err}") from err
        except ClientError as err:
            _LOGGER.error("Connection error: %s", err)
            raise KoreWirelessConnectionError(f"Connection error: {err}") from err

    async def test_connection(self) -> bool:
        """Test the API connection."""
        try:
            await self.get_sims(page_size=1)
            return True
        except KoreWirelessAPIError:
            return False

    async def get_sims(
        self,
        page_size: int = 50,
        page: int | None = None,
        status: str | None = None,
        fleet: str | None = None,
    ) -> dict[str, Any]:
        """Get list of SIMs."""
        params: dict[str, Any] = {"PageSize": page_size}
        if page is not None:
            params["Page"] = page
        if status is not None:
            params["Status"] = status
        if fleet is not None:
            params["Fleet"] = fleet

        return await self._request("GET", "Sims", params=params)

    async def get_sim(self, sid: str) -> dict[str, Any]:
        """Get a specific SIM by SID or unique name."""
        return await self._request("GET", f"Sims/{sid}")

    async def get_sim_billing_periods(
        self,
        sim_sid: str,
        page_size: int = 10,
    ) -> dict[str, Any]:
        """Get billing periods for a SIM."""
        params = {"PageSize": page_size}
        return await self._request("GET", f"Sims/{sim_sid}/BillingPeriods", params=params)

    async def get_usage_records(
        self,
        sim: str | None = None,
        fleet: str | None = None,
        network: str | None = None,
        granularity: str = "day",
        start_time: str | None = None,
        end_time: str | None = None,
        page_size: int = 50,
    ) -> dict[str, Any]:
        """Get usage records."""
        params: dict[str, Any] = {
            "PageSize": page_size,
            "Granularity": granularity,
        }
        if sim is not None:
            params["Sim"] = sim
        if fleet is not None:
            params["Fleet"] = fleet
        if network is not None:
            params["Network"] = network
        if start_time is not None:
            params["StartTime"] = start_time
        if end_time is not None:
            params["EndTime"] = end_time

        return await self._request("GET", "UsageRecords", params=params)

    async def get_fleets(self, page_size: int = 50) -> dict[str, Any]:
        """Get list of fleets."""
        params = {"PageSize": page_size}
        return await self._request("GET", "Fleets", params=params)

    async def get_fleet(self, sid: str) -> dict[str, Any]:
        """Get a specific fleet."""
        return await self._request("GET", f"Fleets/{sid}")

    async def get_networks(self, page_size: int = 50) -> dict[str, Any]:
        """Get list of networks."""
        params = {"PageSize": page_size}
        return await self._request("GET", "Networks", params=params)

    async def get_sms_commands(
        self,
        sim: str | None = None,
        status: str | None = None,
        direction: str | None = None,
        page_size: int = 50,
    ) -> dict[str, Any]:
        """Get SMS commands."""
        params: dict[str, Any] = {"PageSize": page_size}
        if sim is not None:
            params["Sim"] = sim
        if status is not None:
            params["Status"] = status
        if direction is not None:
            params["Direction"] = direction

        return await self._request("GET", "SmsCommands", params=params)

    async def send_sms_command(
        self,
        sim: str,
        payload: str,
        callback_url: str | None = None,
    ) -> dict[str, Any]:
        """Send an SMS command to a SIM."""
        data: dict[str, Any] = {
            "Sim": sim,
            "Payload": payload,
        }
        if callback_url is not None:
            data["CallbackUrl"] = callback_url

        return await self._request("POST", "SmsCommands", data=data)

    async def update_sim(
        self,
        sid: str,
        status: str | None = None,
        fleet: str | None = None,
        unique_name: str | None = None,
        account_sid: str | None = None,
    ) -> dict[str, Any]:
        """Update a SIM's properties."""
        data: dict[str, Any] = {}
        if status is not None:
            data["Status"] = status
        if fleet is not None:
            data["Fleet"] = fleet
        if unique_name is not None:
            data["UniqueName"] = unique_name
        if account_sid is not None:
            data["AccountSid"] = account_sid

        return await self._request("POST", f"Sims/{sid}", data=data)

    async def get_all_sims(self) -> list[dict[str, Any]]:
        """Get all SIMs (handles pagination)."""
        all_sims: list[dict[str, Any]] = []
        page = 0

        while True:
            response = await self.get_sims(page_size=50, page=page)
            sims = response.get("sims", [])
            if not sims:
                break
            all_sims.extend(sims)

            # Check if there are more pages
            meta = response.get("meta", {})
            if not meta.get("next_page_url"):
                break
            page += 1

        return all_sims
