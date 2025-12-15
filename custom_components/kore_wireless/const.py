"""Constants for the Kore Wireless SuperSIM integration."""
from typing import Final

DOMAIN: Final = "kore_wireless"

# API
API_BASE_URL: Final = "https://supersim.api.korewireless.com/v1"

# Config
CONF_API_TOKEN: Final = "api_token"

# Defaults
DEFAULT_SCAN_INTERVAL: Final = 300  # 5 minutes

# SIM Statuses
SIM_STATUS_NEW: Final = "new"
SIM_STATUS_READY: Final = "ready"
SIM_STATUS_ACTIVE: Final = "active"
SIM_STATUS_INACTIVE: Final = "inactive"
SIM_STATUS_SCHEDULED: Final = "scheduled"
