# Kore Wireless SuperSIM Integration for Home Assistant

[![hacs_badge](https://img.shields.io/badge/HACS-Custom-41BDF5.svg)](https://github.com/hacs/integration)
[![GitHub Release](https://img.shields.io/github/release/manjotsc/ha-kore_wireless.svg)](https://github.com/manjotsc/ha-kore_wireless/releases)
[![License](https://img.shields.io/github/license/manjotsc/ha-kore_wireless.svg)](LICENSE)

A custom Home Assistant integration to monitor and manage your Kore Wireless SuperSIM devices.

## Features

- **Multi-SIM Support**: Monitor multiple SuperSIM devices from a single integration
- **Real-time Status**: Track SIM active/inactive status
- **Usage Monitoring**: Data upload, download, and total usage per SIM
- **SMS Management**: Send SMS messages and view SMS history with received/sent counts
- **Network Information**: Current network operator and country
- **Fleet Management**: See which fleet each SIM belongs to
- **Billing Period Tracking**: View billing period start and end dates
- **OTA Updates**: Monitor pending over-the-air settings updates
- **IP Address**: View assigned IP address (VPN-enabled fleets only)
- **Account Overview**: Total SIMs, active SIMs, and aggregate statistics
- **OAuth2 Authentication**: Secure authentication with automatic token refresh
- **Easy Setup**: Configure via manual entry or CSV file upload

## Entities

### Per-SIM Device

Each SIM appears as a device with the following entities:

| Entity Type | Name | Description |
|-------------|------|-------------|
| Binary Sensor | Active | Whether the SIM is active (on/off) |
| Sensor | Status | SIM status (new/ready/active/inactive/scheduled) |
| Sensor | ICCID | SIM ICCID identifier |
| Sensor | Fleet | Fleet name the SIM belongs to |
| Sensor | Data Download | Current period data download in MB |
| Sensor | Data Upload | Current period data upload in MB |
| Sensor | Data Total | Current period total data usage in MB |
| Sensor | SMS Received | Number of SMS messages received from device |
| Sensor | SMS Sent | Number of SMS messages sent to device |
| Sensor | SMS Total | Total SMS message count |
| Sensor | Network Operator | Current network operator name |
| Sensor | Network Country | Current network country code |
| Sensor | IP Address | Assigned IP address (or "VPN required") |
| Sensor | Pending OTA Updates | Number of pending settings updates |
| Sensor | Billing Period Start | Current billing period start date |
| Sensor | Billing Period End | Current billing period end date |
| Button | Activate | Activate the SIM (when inactive) |
| Button | Deactivate | Deactivate the SIM (when active) |

### Account-Level Entities

| Entity Type | Name | Description |
|-------------|------|-------------|
| Sensor | Total SIMs | Total number of SIMs in your account |
| Sensor | Active SIMs | Number of currently active SIMs |
| Sensor | Total Data Upload | Combined data upload across all SIMs |
| Sensor | Total Data Download | Combined data download across all SIMs |
| Sensor | Total Data Usage | Combined total data usage across all SIMs |
| Sensor | Total SMS Received | Combined SMS received across all SIMs |
| Sensor | Total SMS Sent | Combined SMS sent across all SIMs |
| Sensor | Total SMS | Combined total SMS across all SIMs |
| Sensor | Total Pending OTA Updates | Combined pending updates across all SIMs |
| Button | Refresh Data | Manually refresh all data |

## Services

### Send SMS

Send an SMS message to a SIM card.

```yaml
service: kore_wireless.send_sms
data:
  device_id: <device_id>
  message: "Hello from Home Assistant!"
  callback_url: "https://your-callback-url.com"  # Optional
```

### Get SMS Commands

Retrieve SMS command history for a SIM card.

```yaml
service: kore_wireless.get_sms_commands
data:
  device_id: <device_id>
  direction: "to_sim"  # Optional: to_sim, from_sim
  status: "delivered"  # Optional: queued, sent, delivered, failed
```

## Requirements

- Home Assistant 2024.1.0 or newer
- Kore Wireless account with API access
- API Client ID and Client Secret from [Kore Wireless Developer Console](https://docs.korewireless.com/)

## Installation

### HACS (Recommended)

1. Open HACS in Home Assistant
2. Click on "Integrations"
3. Click the three dots menu in the top right corner
4. Select "Custom repositories"
5. Add `https://github.com/manjotsc/ha-kore_wireless` and select "Integration" as the category
6. Click "Add"
7. Search for "Kore Wireless" and install
8. Restart Home Assistant

### Manual Installation

1. Download or clone this repository
2. Copy the `custom_components/kore_wireless` folder to your Home Assistant `config/custom_components/` directory
3. Restart Home Assistant

## Configuration

### Setup via UI

1. Go to **Settings** > **Devices & Services**
2. Click **+ Add Integration**
3. Search for "Kore Wireless SuperSIM"
4. Choose setup method:
   - **Enter credentials manually**: Enter Client ID and Client Secret
   - **Upload credentials CSV file**: Upload the CSV exported from Kore Wireless
5. Click **Submit**

### Getting Your API Credentials

1. Log in to the [Kore Wireless Console](https://www.korewireless.com/)
2. Navigate to the API credentials or developer section
3. Create a new API client if you haven't already
4. Download the credentials CSV file or copy your **Client ID** and **Client Secret**
   - Note: The Client Secret cannot be retrieved after initial creation, so save it securely
5. Use these credentials when configuring the integration

### Options

After setup, you can configure additional options:

1. Go to **Settings** > **Devices & Services**
2. Find the Kore Wireless integration and click **Configure**
3. Available options:
   - **Update interval**: 60-3600 seconds (default: 300 seconds)
   - **Enable activate/deactivate buttons**: Show SIM control buttons
   - **Enable account-level sensors**: Show aggregate account sensors
   - **SIM sensors to enable**: Select which sensors to create per SIM

## Usage Examples

### Automation: Alert on SIM Deactivation

```yaml
automation:
  - alias: "Alert when SIM becomes inactive"
    trigger:
      - platform: state
        entity_id: binary_sensor.sim_my_device_active
        to: "off"
    action:
      - service: notify.mobile_app
        data:
          title: "SIM Alert"
          message: "SIM is now inactive"
```

### Automation: Monitor High Data Usage

```yaml
automation:
  - alias: "Alert on high data usage"
    trigger:
      - platform: numeric_state
        entity_id: sensor.sim_my_device_data_total
        above: 1000  # 1 GB
    action:
      - service: notify.mobile_app
        data:
          title: "Data Usage Alert"
          message: "SIM has exceeded 1 GB of data usage"
```

### Automation: Send SMS on Event

```yaml
automation:
  - alias: "Send SMS when door opens"
    trigger:
      - platform: state
        entity_id: binary_sensor.front_door
        to: "on"
    action:
      - service: kore_wireless.send_sms
        data:
          device_id: <your_sim_device_id>
          message: "Alert: Front door opened!"
```

### Automation: Alert on Billing Period End

```yaml
automation:
  - alias: "Alert before billing period ends"
    trigger:
      - platform: template
        value_template: >
          {{ (as_timestamp(states('sensor.sim_my_device_billing_period_end')) - as_timestamp(now())) < 86400 }}
    action:
      - service: notify.mobile_app
        data:
          title: "Billing Alert"
          message: "SIM billing period ends in less than 24 hours"
```

### Dashboard Card Example

```yaml
type: entities
title: Kore Wireless SIMs
entities:
  - entity: sensor.kore_wireless_account_total_sims
  - entity: sensor.kore_wireless_account_active_sims
  - entity: sensor.kore_wireless_account_account_data_total
  - type: divider
  - entity: binary_sensor.sim_my_device_active
  - entity: sensor.sim_my_device_status
  - entity: sensor.sim_my_device_data_total
  - entity: sensor.sim_my_device_network_operator
  - entity: sensor.sim_my_device_network_country
```

## API Reference

This integration uses the [Kore Wireless SuperSIM REST API](https://docs.korewireless.com/):

- **Base URL**: `https://supersim.api.korewireless.com/v1`
- **Auth URL**: `https://api.korewireless.com/api-services/v1/auth/token`
- **Authentication**: OAuth2 Client Credentials

### Endpoints Used

| Endpoint | Description |
|----------|-------------|
| `GET /Sims` | List all SIMs |
| `GET /Sims/{sid}` | Get specific SIM |
| `POST /Sims/{sid}` | Update SIM status |
| `GET /Sims/{sid}/BillingPeriods` | Get billing periods |
| `GET /Sims/{sid}/IpAddresses` | Get IP addresses |
| `GET /UsageRecords` | Get usage data |
| `GET /Fleets` | List fleets |
| `GET /Networks` | List networks |
| `GET /Networks/{sid}` | Get specific network |
| `GET /SmsCommands` | List SMS commands |
| `POST /SmsCommands` | Send SMS command |
| `GET /SettingsUpdates` | Get OTA updates |

## Troubleshooting

### Integration not loading

- Check Home Assistant logs for errors
- Verify your Client ID and Client Secret are correct
- Ensure you have network connectivity to Kore Wireless API

### No data showing

- Verify your SIMs are properly set up in Kore Wireless
- Check that your API client has the necessary permissions
- Wait for the first update cycle (default: 5 minutes)

### Authentication errors

- Regenerate your Client Secret in the Kore Wireless Developer Console
- Remove and re-add the integration with the new credentials
- Note: Client Secrets cannot be retrieved after creation, only regenerated

### Network operator/country showing unknown

- Network information is only available after the SIM has data usage
- Ensure the SIM has been used for data connectivity

### IP address showing "VPN required"

- IP addresses are only available for SIMs in VPN-enabled fleets
- Contact Kore Wireless to enable VPN features if needed

### SMS not sending

- Verify your API client has SMS permissions
- Check the SIM is active and capable of receiving SMS
- SMS payload is limited to 160 characters

## Contributing

Contributions are welcome! Please feel free to submit issues or pull requests.

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Submit a pull request

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## Disclaimer

This is an unofficial integration and is not affiliated with, endorsed by, or supported by Kore Wireless. Use at your own risk.
