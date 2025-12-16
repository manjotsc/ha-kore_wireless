"""Constants for the Kore Wireless SuperSIM integration."""
from typing import Final

DOMAIN: Final = "kore_wireless"

# API URLs
API_BASE_URL: Final = "https://supersim.api.korewireless.com/v1"
AUTH_TOKEN_URL: Final = "https://api.korewireless.com/api-services/v1/auth/token"

# Config keys
CONF_CLIENT_ID: Final = "client_id"
CONF_CLIENT_SECRET: Final = "client_secret"

# Option keys
CONF_ENABLE_BUTTONS: Final = "enable_buttons"
CONF_ENABLE_SIM_SENSORS: Final = "enable_sim_sensors"
CONF_ENABLE_ACCOUNT_SENSORS: Final = "enable_account_sensors"

# Sensor option keys (per-SIM)
CONF_SENSOR_STATUS: Final = "sensor_status"
CONF_SENSOR_ICCID: Final = "sensor_iccid"
CONF_SENSOR_FLEET: Final = "sensor_fleet"
CONF_SENSOR_DATA_DOWNLOAD: Final = "sensor_data_download"
CONF_SENSOR_DATA_UPLOAD: Final = "sensor_data_upload"
CONF_SENSOR_DATA_TOTAL: Final = "sensor_data_total"
CONF_SENSOR_SMS_COUNT: Final = "sensor_sms_count"
CONF_SENSOR_NETWORK_OPERATOR: Final = "sensor_network_operator"
CONF_SENSOR_NETWORK_COUNTRY: Final = "sensor_network_country"
CONF_SENSOR_IP_ADDRESS: Final = "sensor_ip_address"

# Defaults
DEFAULT_SCAN_INTERVAL: Final = 300  # 5 minutes
DEFAULT_ENABLE_BUTTONS: Final = True
DEFAULT_ENABLE_SIM_SENSORS: Final = True
DEFAULT_ENABLE_ACCOUNT_SENSORS: Final = True

# SIM Statuses
SIM_STATUS_NEW: Final = "new"
SIM_STATUS_READY: Final = "ready"
SIM_STATUS_ACTIVE: Final = "active"
SIM_STATUS_INACTIVE: Final = "inactive"
SIM_STATUS_SCHEDULED: Final = "scheduled"
