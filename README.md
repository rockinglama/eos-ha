<div align="center">
  <img src="icon.jpg" alt="EOS-HA Logo" width="200"/>

  # EOS-HA

  [![Add to HACS](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=rockinglama&repository=eos-ha&category=integration)

  A Home Assistant custom integration for [Akkudoktor EOS](https://github.com/Akkudoktor-EOS/EOS) energy optimization. EOS-HA connects your Home Assistant energy data to an EOS optimization server and exposes the results as HA entities you can use in automations and dashboards.
</div>

## What It Does

EOS-HA runs an optimization cycle every 5 minutes:

1. **Collects** electricity prices, battery SOC, and consumption from your HA entities
2. **Fetches** a 48-hour PV forecast from the Akkudoktor API (supports multiple PV arrays)
3. **Sends** all data to your EOS server for optimization
4. **Exposes** the results (charge/discharge recommendations, forecasts, costs) as HA entities

You keep full control — EOS-HA provides recommendations as sensor entities. You decide how to act on them with your own automations.

## Requirements

- Home Assistant 2024.1+
- A running [Akkudoktor EOS](https://github.com/Akkudoktor-EOS/EOS) server (reachable from HA)
- An electricity price sensor in HA (e.g. Tibber, ENTSO-E)
- A battery SOC sensor
- A consumption/load sensor

## Installation

### HACS (Recommended)

1. Click the badge above, or go to **HACS → Integrations → ⋮ → Custom repositories**
2. Add `https://github.com/rockinglama/eos-ha` as an Integration
3. Search for **EOS HA** and install
4. Restart Home Assistant

### Manual

1. Copy `custom_components/eos_ha/` to your HA `config/custom_components/` directory
2. Restart Home Assistant

## Configuration

Add the integration via **Settings → Devices & Services → + Add Integration → EOS HA**.

The setup wizard guides you through 4 steps:

1. **EOS Server URL** — URL of your EOS server (e.g. `http://192.168.1.94:8503`)
2. **Entity Selection** — Pick HA entities for electricity price, battery SOC, and consumption
3. **Battery Parameters** — Capacity (kWh), max charge power (W), SOC limits (%), inverter power (W)
4. **PV Arrays** — Add your solar arrays with azimuth, tilt, peak power, and inverter power

All parameters can be changed at any time via **Options** (no need to delete and re-add).

### PV Array Configuration

EOS-HA supports **multiple PV arrays** for systems with panels on different roof faces:

| Parameter | Description | Example |
|-----------|-------------|---------|
| Azimuth | Panel orientation (0°=N, 90°=E, 180°=S, 270°=W) | 180° |
| Tilt | Panel angle from horizontal | 35° |
| Peak Power | Installed capacity in Wp | 5000 Wp |
| Inverter Power | Inverter rating in W | 5000 W |

## Entities

### Sensors

| Entity | Description |
|--------|-------------|
| `sensor.eos_optimization_status` | Optimization state: `optimized`, `failed`, `unknown` |
| `sensor.eos_*_ac_charge_power` | Recommended AC charge power (W) for current hour |
| `sensor.eos_*_dc_charge_power` | Recommended DC charge power (W) for current hour |
| `sensor.eos_*_current_mode` | Current mode: `charge`, `discharge`, `idle` |
| `sensor.eos_*_total_cost` | Total optimized cost (€) |
| `sensor.eos_*_pv_forecast` | Current hour PV forecast (W), 48h forecast in attributes |
| `sensor.eos_*_price_forecast` | Current hour price (€/Wh), 48h forecast in attributes |
| `sensor.eos_*_consumption_forecast` | Current hour consumption (W), 48h in attributes |
| `sensor.eos_*_battery_soc_forecast` | Current hour SOC (%), 48h forecast in attributes |

### Binary Sensors

| Entity | Description |
|--------|-------------|
| `binary_sensor.eos_*_discharge_allowed` | Whether battery discharge is allowed this hour |

### Number Entities

Adjustable at runtime — changes take effect on the next optimization cycle:

| Entity | Description | Range |
|--------|-------------|-------|
| `number.eos_*_battery_capacity` | Battery capacity | 0.1–100 kWh |
| `number.eos_*_max_charge_power` | Max charge power | 100–50000 W |
| `number.eos_*_inverter_power` | Inverter power | 100–50000 W |
| `number.eos_*_minimum_soc` | Minimum SOC limit | 0–100% |
| `number.eos_*_maximum_soc` | Maximum SOC limit | 0–100% |

## Services

### `eos_ha.optimize_now`

Trigger an immediate optimization cycle (instead of waiting for the 5-minute interval).

### `eos_ha.set_override`

Manually override the optimization mode:

| Parameter | Description |
|-----------|-------------|
| `mode` | `charge` (force charge), `discharge` (force discharge), `auto` (clear override) |
| `duration` | Duration in minutes (1–1440, default: 60) |

**Example automation:**
```yaml
service: eos_ha.set_override
data:
  mode: charge
  duration: 120
```

## 48-Hour Forecasts

All forecast sensors expose a `forecast` attribute containing the full 48-hour hourly forecast array. Use this in Apex Charts or template sensors:

```yaml
type: custom:apexcharts-card
series:
  - entity: sensor.eos_energy_optimizer_pv_forecast
    data_generator: |
      return entity.attributes.forecast.map((val, idx) => {
        const date = new Date();
        date.setMinutes(0, 0, 0);
        date.setHours(date.getHours() + idx);
        return [date.getTime(), val];
      });
```

## Diagnostics

Download diagnostics via **Settings → Devices & Services → EOS HA → ⋮ → Download Diagnostics**. Sensitive data (coordinates, server URL) is automatically redacted.

## License

MIT License — see [LICENSE](LICENSE) for details.
