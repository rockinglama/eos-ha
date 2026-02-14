<div align="center">
  <img src="icon.jpg" alt="EOS-HA Logo" width="200"/>

  # EOS-HA

  [![Add to HACS](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=rockinglama&repository=eos-ha&category=integration)

  A Home Assistant custom integration for [Akkudoktor EOS](https://github.com/Akkudoktor-EOS/EOS) energy optimization. EOS-HA connects your Home Assistant energy data to an EOS optimization server and exposes the results as HA entities you can use in automations and dashboards.
</div>

## What It Does

EOS-HA runs an optimization cycle every 5 minutes:

1. **Collects** electricity prices, battery SOC, and consumption from your HA entities
2. **Fetches** a 48-hour PV forecast from the Akkudoktor API
3. **Sends** all data to your EOS server for optimization
4. **Exposes** the results (charge/discharge recommendations, forecasts) as HA entities

You keep full control — EOS-HA provides recommendations as sensor entities. You decide how to act on them with your own automations.

## Requirements

- Home Assistant
- A running [Akkudoktor EOS](https://github.com/Akkudoktor-EOS/EOS) server (reachable from HA)
- An electricity price sensor in HA (e.g. Tibber integration)
- A battery SOC sensor
- A consumption/load sensor

## Installation

### HACS (Recommended)

1. Click the badge above, or go to **HACS > Integrations > + Explore & Download Repositories**
2. Search for **EOS-HA** and install
3. Restart Home Assistant

### Manual

1. Copy `custom_components/eos_ha/` to your HA `config/custom_components/` directory
2. Restart Home Assistant

## Configuration

After installation, add the integration via **Settings > Devices & Services > + Add Integration > EOS-HA**.

The setup wizard has 3 steps:

1. **EOS Server URL** — Enter the URL of your EOS server (e.g. `http://192.168.1.94:8503`). The integration validates the server is reachable.
2. **Entity Selection** — Pick your HA entities for electricity price, battery SOC, and consumption/load.
3. **Battery Parameters** — Enter your battery capacity (kWh), max charge power (W), SOC limits (%), and inverter power (W). Sensible defaults are pre-filled.

Your home location (latitude/longitude) is pulled automatically from your HA configuration.

## Entities

| Entity | Type | Description |
|--------|------|-------------|
| EOS Optimization Status | Sensor | Shows `optimized`, `failed`, or `unknown` with last update timestamp |

More entities (charge power, discharge control, forecasts) are coming in future releases.

## License

MIT License - see [LICENSE](LICENSE) for details.
