"""Kore Wireless SuperSIM API client."""
from __future__ import annotations

import logging
import time
from typing import Any

import aiohttp
from aiohttp import ClientError, ClientResponseError

from .const import API_BASE_URL, AUTH_TOKEN_URL

_LOGGER = logging.getLogger(__name__)


class KoreWirelessAPIError(Exception):
    """Base exception for Kore Wireless API errors."""


class KoreWirelessAuthError(KoreWirelessAPIError):
    """Authentication error."""


class KoreWirelessConnectionError(KoreWirelessAPIError):
    """Connection error."""


class KoreWirelessAPI:
    """Kore Wireless SuperSIM API client with OAuth2 authentication."""

    def __init__(
        self,
        session: aiohttp.ClientSession,
        client_id: str,
        client_secret: str,
    ) -> None:
        """Initialize the API client."""
        self._session = session
        self._client_id = client_id
        self._client_secret = client_secret
        self._access_token: str | None = None
        self._token_expires_at: float = 0

    async def _get_access_token(self) -> str:
        """Get a valid access token, refreshing if necessary."""
        # Check if we have a valid token (with 60 second buffer)
        if self._access_token and time.time() < (self._token_expires_at - 60):
            return self._access_token

        # Request new token
        try:
            async with self._session.post(
                AUTH_TOKEN_URL,
                headers={
                    "Content-Type": "application/x-www-form-urlencoded",
                    "Cache-Control": "no-cache",
                },
                data={
                    "grant_type": "client_credentials",
                    "client_id": self._client_id,
                    "client_secret": self._client_secret,
                },
            ) as response:
                if response.status == 401:
                    raise KoreWirelessAuthError("Invalid client credentials")
                if response.status == 403:
                    raise KoreWirelessAuthError("Access forbidden")

                response.raise_for_status()
                data = await response.json()

                self._access_token = data.get("access_token")
                expires_in = int(data.get("expires_in", 3600))
                self._token_expires_at = time.time() + expires_in

                _LOGGER.debug("Obtained new access token, expires in %d seconds", expires_in)

                if not self._access_token:
                    raise KoreWirelessAuthError("No access token in response")

                return self._access_token

        except ClientResponseError as err:
            _LOGGER.error("Token request failed: %s", err)
            raise KoreWirelessAuthError(f"Token request failed: {err}") from err
        except ClientError as err:
            _LOGGER.error("Connection error during token request: %s", err)
            raise KoreWirelessConnectionError(f"Connection error: {err}") from err

    async def _request(
        self,
        method: str,
        endpoint: str,
        params: dict[str, Any] | None = None,
        data: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Make an API request with automatic token handling."""
        url = f"{API_BASE_URL}/{endpoint}"

        # Get valid access token
        access_token = await self._get_access_token()

        headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json",
        }

        try:
            async with self._session.request(
                method,
                url,
                headers=headers,
                params=params,
                json=data,
            ) as response:
                if response.status == 401:
                    # Token might have expired, clear it and retry once
                    self._access_token = None
                    self._token_expires_at = 0
                    access_token = await self._get_access_token()
                    headers["Authorization"] = f"Bearer {access_token}"

                    async with self._session.request(
                        method,
                        url,
                        headers=headers,
                        params=params,
                        json=data,
                    ) as retry_response:
                        if retry_response.status == 401:
                            raise KoreWirelessAuthError("Invalid credentials")
                        retry_response.raise_for_status()
                        return await retry_response.json()

                if response.status == 403:
                    raise KoreWirelessAuthError("Access forbidden")

                response.raise_for_status()
                result = await response.json()
                _LOGGER.debug("API response for %s: %s", endpoint, result)
                return result

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
        iso_country: str | None = None,
        group: str | None = None,
        granularity: str | None = None,
        start_time: str | None = None,
        end_time: str | None = None,
        page_size: int = 50,
    ) -> dict[str, Any]:
        """Get usage records.

        Args:
            sim: Filter by SIM SID
            fleet: Filter by Fleet SID
            network: Filter by Network SID
            iso_country: Filter by ISO country code
            group: Group by dimension (sim, fleet, network, isoCountry)
            granularity: Time grouping (hour, day, all)
            start_time: ISO 8601 start time
            end_time: ISO 8601 end time
            page_size: Number of results per page
        """
        params: dict[str, Any] = {
            "PageSize": page_size,
        }
        if sim is not None:
            params["Sim"] = sim
        if fleet is not None:
            params["Fleet"] = fleet
        if network is not None:
            params["Network"] = network
        if iso_country is not None:
            params["IsoCountry"] = iso_country
        if group is not None:
            params["Group"] = group
        if granularity is not None:
            params["Granularity"] = granularity
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

    async def get_network(self, sid: str) -> dict[str, Any]:
        """Get a specific network by SID."""
        return await self._request("GET", f"Networks/{sid}")

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
        callback_method: str | None = None,
    ) -> dict[str, Any]:
        """Send an SMS command to a SIM.

        Note: This endpoint requires form-urlencoded data, not JSON.
        """
        url = f"{API_BASE_URL}/SmsCommands"
        access_token = await self._get_access_token()

        headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/x-www-form-urlencoded",
        }

        form_data: dict[str, str] = {
            "Sim": sim,
            "Payload": payload,
        }
        if callback_url is not None:
            form_data["CallbackUrl"] = callback_url
        if callback_method is not None:
            form_data["CallbackMethod"] = callback_method

        try:
            async with self._session.post(
                url,
                headers=headers,
                data=form_data,
            ) as response:
                if response.status == 401:
                    # Token might have expired, retry once
                    self._access_token = None
                    self._token_expires_at = 0
                    access_token = await self._get_access_token()
                    headers["Authorization"] = f"Bearer {access_token}"

                    async with self._session.post(
                        url,
                        headers=headers,
                        data=form_data,
                    ) as retry_response:
                        if retry_response.status == 401:
                            raise KoreWirelessAuthError("Invalid credentials")
                        retry_response.raise_for_status()
                        return await retry_response.json()

                if response.status == 403:
                    raise KoreWirelessAuthError("Access forbidden")

                response.raise_for_status()
                result = await response.json()
                _LOGGER.debug("SMS command response: %s", result)
                return result

        except ClientResponseError as err:
            _LOGGER.error("SMS command failed: %s", err)
            raise KoreWirelessAPIError(f"SMS command failed: {err}") from err
        except ClientError as err:
            _LOGGER.error("Connection error sending SMS: %s", err)
            raise KoreWirelessConnectionError(f"Connection error: {err}") from err

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

    async def get_sim_ip_addresses(self, sim_sid: str) -> dict[str, Any]:
        """Get IP addresses for a SIM."""
        return await self._request("GET", f"Sims/{sim_sid}/IpAddresses")

    async def get_network(self, sid: str) -> dict[str, Any]:
        """Get a specific network by SID."""
        return await self._request("GET", f"Networks/{sid}")

    async def activate_sim(self, sid: str) -> dict[str, Any]:
        """Activate a SIM (set status to active)."""
        return await self.update_sim(sid, status="active")

    async def deactivate_sim(self, sid: str) -> dict[str, Any]:
        """Deactivate a SIM (set status to inactive)."""
        return await self.update_sim(sid, status="inactive")

    async def get_account_usage_records(
        self,
        start: str | None = None,
        end: str | None = None,
        granularity: str = "day",
        page_size: int = 50,
    ) -> dict[str, Any]:
        """Get account-level usage records."""
        params: dict[str, Any] = {
            "PageSize": page_size,
            "Granularity": granularity,
        }
        if start is not None:
            params["Start"] = start
        if end is not None:
            params["End"] = end

        return await self._request("GET", "UsageRecords", params=params)

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
