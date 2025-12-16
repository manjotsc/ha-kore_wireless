# Kore Wireless SuperSIM for Home Assistant

[![HACS Custom](https://img.shields.io/badge/HACS-Custom-41BDF5.svg)](https://github.com/hacs/integration)
[![GitHub Release](https://img.shields.io/github/release/manjotsc/ha-kore_wireless.svg)](https://github.com/manjotsc/ha-kore_wireless/releases)

> **Disclaimer**: This is an unofficial, community-maintained integration and is not affiliated with, endorsed by, or supported by Kore Wireless. Use at your own risk.

Monitor and manage your Kore Wireless SuperSIM devices in Home Assistant.

## Features

- Multi-SIM monitoring with real-time status
- Data usage tracking (upload/download/total)
- SMS send & receive with history
- Network operator & country detection
- Billing period tracking
- OTA update monitoring
- Activate/deactivate SIM controls

## Installation

### HACS (Recommended)

1. Open HACS → Integrations → Menu (⋮) → Custom repositories
2. Add `https://github.com/manjotsc/ha-kore_wireless` as Integration
3. Search "Kore Wireless" and install
4. Restart Home Assistant

### Manual

Copy `custom_components/kore_wireless` to your `config/custom_components/` directory.

## Setup

1. Go to **Settings** → **Devices & Services** → **Add Integration**
2. Search "Kore Wireless SuperSIM"
3. Enter credentials manually or upload CSV from Kore Wireless console

## Entities

### Per SIM
| Type | Entities |
|------|----------|
| Sensors | Status, ICCID, Fleet, Data (Upload/Download/Total), SMS (Received/Sent/Total), Network Operator, Network Country, IP Address, Pending OTA Updates, Billing Period (Start/End) |
| Binary Sensor | Active |
| Buttons | Activate, Deactivate |

### Account Level
| Type | Entities |
|------|----------|
| Sensors | Total SIMs, Active SIMs, Total Data Usage, Total SMS, Total Pending Updates |
| Button | Refresh Data |

## Services

```yaml
# Send SMS
service: kore_wireless.send_sms
data:
  device_id: <device_id>
  message: "Hello from Home Assistant!"

# Get SMS history
service: kore_wireless.get_sms_commands
data:
  device_id: <device_id>
```

## Options

Configure via integration options:
- Update interval (60-3600 seconds)
- Enable/disable activate/deactivate buttons
- Enable/disable account-level sensors
- Select which SIM sensors to enable

## Requirements

- Home Assistant 2024.1.0+
- Kore Wireless API credentials ([Get credentials](https://docs.korewireless.com/))

## License

MIT License - see [LICENSE](LICENSE)
