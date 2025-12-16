# Kore Wireless SuperSIM Integration for Home Assistant

A custom Home Assistant integration to monitor your Kore Wireless SuperSIM devices.

## Features

- **Multi-SIM Support**: Monitor multiple SuperSIM devices from a single integration
- **Real-time Status**: Track SIM active/inactive status
- **Usage Monitoring**: Data usage and SMS count per SIM
- **Fleet Management**: See which fleet each SIM belongs to
- **Location Tracking**: Device tracker entities for SIM location (when available)
- **Account Overview**: Total SIMs, active SIMs, and aggregate data usage
- **OAuth2 Authentication**: Secure authentication with automatic token refresh

## Entities

### Per-SIM Device

Each SIM appears as a device with the following entities:

| Entity Type | Name | Description |
|-------------|------|-------------|
| Binary Sensor | Active | Whether the SIM is active (on/off) |
| Sensor | Status | SIM status (new/ready/active/inactive/scheduled) |
| Sensor | ICCID | SIM ICCID identifier |
| Sensor | Fleet | Fleet name the SIM belongs to |
| Sensor | Data Usage | Current period data usage in MB |
| Sensor | SMS Count | Number of SMS messages |
| Device Tracker | Location | SIM location based on network data |

### Account-Level Sensors

| Entity Type | Name | Description |
|-------------|------|-------------|
| Sensor | Total SIMs | Total number of SIMs in your account |
| Sensor | Active SIMs | Number of currently active SIMs |
| Sensor | Total Data Usage | Combined data usage across all SIMs |

## Requirements

- Home Assistant 2024.1.0 or newer
- Kore Wireless account with API access
- API Client ID and Client Secret from [Kore Wireless Developer Console](https://docs.korewireless.com/en-us/developers/get-started/apis)

## Installation

### HACS (Recommended)

1. Open HACS in Home Assistant
2. Click on "Integrations"
3. Click the three dots menu in the top right corner
4. Select "Custom repositories"
5. Add this repository URL and select "Integration" as the category
6. Click "Add"
7. Search for "Kore Wireless" and install
8. Restart Home Assistant

### Manual Installation

1. Download or clone this repository
2. Copy the `custom_components/kore_wireless` folder to your Home Assistant `config/custom_components/` directory
3. Restart Home Assistant

## Configuration

### Setup via UI

1. Go to **Settings** → **Devices & Services**
2. Click **+ Add Integration**
3. Search for "Kore Wireless SuperSIM"
4. Enter your **Client ID** and **Client Secret**
5. Click **Submit**

### Getting Your API Credentials

1. Log in to the [Kore Wireless Developer Console](https://www.korewireless.com/)
2. Navigate to the client management section
3. Create a new API client if you haven't already
4. Copy your **Client ID** and **Client Secret**
   - Note: The Client Secret cannot be retrieved after initial creation, so save it securely
5. Use these credentials when configuring the integration

### Options

After setup, you can configure additional options:

1. Go to **Settings** → **Devices & Services**
2. Find the Kore Wireless integration and click **Configure**
3. Adjust the **Update interval** (60-3600 seconds, default: 300 seconds)

## Authentication

This integration uses OAuth2 Client Credentials flow:

1. **Token Endpoint**: `https://api.korewireless.com/api-services/v1/auth/token`
2. **Grant Type**: `client_credentials`
3. **Automatic Refresh**: Tokens are automatically refreshed before expiration

## Usage Examples

### Automation: Alert on SIM Deactivation

```yaml
automation:
  - alias: "Alert when SIM becomes inactive"
    trigger:
      - platform: state
        entity_id: binary_sensor.sim_1234567890_active
        to: "off"
    action:
      - service: notify.mobile_app
        data:
          title: "SIM Alert"
          message: "SIM {{ trigger.to_state.attributes.iccid }} is now inactive"
```

### Automation: Monitor High Data Usage

```yaml
automation:
  - alias: "Alert on high data usage"
    trigger:
      - platform: numeric_state
        entity_id: sensor.sim_1234567890_data_usage
        above: 1000  # 1 GB
    action:
      - service: notify.mobile_app
        data:
          title: "Data Usage Alert"
          message: "SIM has exceeded 1 GB of data usage"
```

### Dashboard Card Example

```yaml
type: entities
title: Kore Wireless SIMs
entities:
  - entity: sensor.kore_wireless_account_total_sims
  - entity: sensor.kore_wireless_account_active_sims
  - entity: sensor.kore_wireless_account_total_data_usage
  - type: divider
  - entity: binary_sensor.sim_your_sim_active
  - entity: sensor.sim_your_sim_status
  - entity: sensor.sim_your_sim_data_usage
```

## API Reference

This integration uses the [Kore Wireless SuperSIM REST API](https://docs.korewireless.com/en-us/api/products/supersim):

- Base URL: `https://supersim.api.korewireless.com/v1`
- Auth URL: `https://api.korewireless.com/api-services/v1/auth/token`
- Authentication: OAuth2 Client Credentials
- Endpoints used:
  - `GET /Sims` - List SIMs
  - `GET /UsageRecords` - Usage data
  - `GET /Fleets` - Fleet information
  - `GET /SmsCommands` - SMS commands

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

### "Invalid client credentials" error

- Double-check that you're using the correct Client ID
- Ensure the Client Secret hasn't been regenerated since setup
- Verify your API client is active in the Kore Wireless console

## Contributing

Contributions are welcome! Please feel free to submit issues or pull requests.

## License

This project is licensed under the MIT License.

## Disclaimer

This is an unofficial integration and is not affiliated with, endorsed by, or supported by Kore Wireless. Use at your own risk.
