"""Constants for the Kore Wireless SuperSIM integration."""
from typing import Final

DOMAIN: Final = "kore_wireless"

# API URLs
API_BASE_URL: Final = "https://supersim.api.korewireless.com/v1"
AUTH_TOKEN_URL: Final = "https://api.korewireless.com/api-services/v1/auth/token"

# Config keys
CONF_CLIENT_ID: Final = "client_id"
CONF_CLIENT_SECRET: Final = "client_secret"

# Defaults
DEFAULT_SCAN_INTERVAL: Final = 300  # 5 minutes

# SIM Statuses
SIM_STATUS_NEW: Final = "new"
SIM_STATUS_READY: Final = "ready"
SIM_STATUS_ACTIVE: Final = "active"
SIM_STATUS_INACTIVE: Final = "inactive"
SIM_STATUS_SCHEDULED: Final = "scheduled"
