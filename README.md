<div align="center">
  <img src="icon.jpg" alt="EOS-HA Logo" width="200"/>

  # EOS-HA

  [![HACS Validation](https://github.com/rockinglama/eos-ha/actions/workflows/validate.yml/badge.svg)](https://github.com/rockinglama/eos-ha/actions/workflows/validate.yml)
  [![Add to HACS](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=rockinglama&repository=eos-ha&category=integration)

  A Home Assistant custom integration for [Akkudoktor EOS](https://github.com/Akkudoktor-EOS/EOS) energy optimization.
</div>

## What It Does

EOS-HA runs an optimization cycle every 5 minutes:

1. **Collects** electricity prices, battery SOC, consumption, and load history from your HA entities
2. **Fetches** a 48-hour PV forecast via the EOS server's native `/pvforecast` endpoint (supports multiple PV arrays)
3. **Pushes** current measurements (SOC + consumption) and 7-day hourly load history from the HA recorder to EOS
4. **Sends** all data to your EOS server for optimization
5. **Exposes** the results (charge/discharge plan, forecasts, costs, EV charge plan, appliance schedules) as HA entities

You keep full control — EOS-HA provides recommendations as sensor entities. You decide how to act on them with your own automations.

## Requirements

- Home Assistant 2024.1+
- A running [Akkudoktor EOS](https://github.com/Akkudoktor-EOS/EOS) server (reachable from HA)
- A battery SOC sensor
- A consumption/load sensor
- An electricity price sensor (only if using "External" price source — see below)

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

### Config Flow (Multi-Step Setup Wizard)

| Step | What You Configure |
|------|--------------------|
| **1. EOS Server URL** | URL of your EOS server (e.g. `http://192.168.1.94:8503`). EOS addon is auto-detected via Supervisor API if running as an add-on. |
| **2. Entities** | HA entities for electricity price (if external), battery SOC, and consumption |
| **3. Battery** | Capacity (kWh), max charge power (W), inverter power (W), SOC limits (%) |
| **4. PV Arrays** | Add one or more solar arrays with azimuth, tilt, peak power, inverter power, efficiency |
| **5. EV (optional)** | Electric vehicle — capacity, charge power, SOC entity, efficiency |
| **6. Appliances (optional)** | Flexible home appliances (e.g. Brauchwasserwärmepumpe) |
| **7. Battery Sensors (optional)** | Entities for battery storage price tracking (grid power, PV power, energy) |

### EOS Addon Auto-Detection

If you run the EOS addon on the same Home Assistant OS instance, the integration automatically detects it via the Supervisor API and pre-fills the server URL — no manual configuration needed.

### Auto-Configuration of EOS Server

At startup, EOS-HA sends your configured battery parameters, PV arrays, and price source to the EOS server via its configuration API, ensuring the server is always in sync with your HA settings.

### Options Flow

All parameters can be changed at any time via **Settings → Devices & Services → EOS HA → Configure**. The options flow presents a menu with sections:

- **Entities** — Update input entity mappings
- **Battery** — Change battery parameters
- **PV Arrays** — Add/edit/remove solar arrays
- **Price Source** — Switch between Akkudoktor, EnergyCharts, or external sensor
- **EV** — Enable/configure electric vehicle
- **Appliances** — Manage flexible loads
- **Battery Sensors** — Configure battery storage price tracking entities
- **Feed-in Tariff** — Adjust feed-in rate

## Price Sources

| Source | Description |
|--------|-------------|
| **Akkudoktor** (default) | Built-in price forecast from EOS/Akkudoktor API |
| **EnergyCharts** | EOS fetches from energy-charts.info (configurable bidding zone, default DE-LU) |
| **External** | Use any HA sensor (Tibber, ENTSO-E, Awattar, etc.) — price in EUR/kWh |

When using Tibber or other external sensors, the integration reads the price from the HA entity state and pushes it to EOS.

## PV Forecast

PV forecasts are fetched via the EOS server's native `/pvforecast` endpoint (not directly from Akkudoktor API). The integration sends your configured PV array parameters (azimuth, tilt, peak power, inverter power, efficiency) to EOS, which handles the forecast calculation. Supports **multiple PV arrays** for systems with panels on different roof faces.

## Measurement Push

Each optimization cycle pushes current data to EOS:

- **SOC measurement** — Current battery state of charge
- **Consumption measurement** — Current household consumption

### Load History Push

The integration queries the HA recorder for the last **7 days of hourly consumption statistics** and pushes them to EOS as historical load data. This improves consumption forecast accuracy.

## Entities

### Sensors

| Entity | Description |
|--------|-------------|
| `optimization_status` | Optimization state: `optimized`, `failed`, `unknown` |
| `ac_charge_power` | Recommended AC charge power (W) for current hour; 48h forecast in attributes |
| `dc_charge_power` | Recommended DC charge power (W) for current hour; 48h forecast in attributes |
| `current_mode` | Current mode: `Grid Charge`, `Allow Discharge`, `Avoid Discharge`, or override |
| `pv_forecast` | Current hour PV forecast (W); 48h forecast in attributes |
| `price_forecast` | Current hour price (EUR/Wh); 48h forecast in attributes |
| `consumption_forecast` | Current hour consumption forecast (W); 48h forecast in attributes |
| `battery_soc_forecast` | Current hour SOC (%); 48h forecast in attributes |
| `override_status` | Active manual override (`charge`, `discharge`, or `none`) |
| `total_cost` | Total optimized cost (EUR) |
| `energy_plan` | Current operation mode from energy plan; full plan in attributes |
| `battery_resource_status` | Battery resource availability (`available`/`unavailable`) |
| `ev_charge_plan` | EV charge plan status (`active`/`inactive`); plan details in attributes |
| `appliance_schedule` | Number of scheduled appliances; schedule details in attributes |
| `battery_storage_price` | Weighted average cost of stored energy (EUR/kWh) — only if battery sensors configured |

All entity IDs are prefixed with `sensor.eos_energy_optimizer_` (based on the default device name "EOS Energy Optimizer").

### Binary Sensors

| Entity | Description |
|--------|-------------|
| `discharge_allowed` | Whether battery discharge is allowed this hour |

### Number Entities

Adjustable at runtime — changes take effect on the next optimization cycle:

| Entity | Description | Range |
|--------|-------------|-------|
| `battery_capacity` | Battery capacity | 0.1–100 kWh |
| `max_charge_power` | Max charge power | 100–50000 W |
| `inverter_power` | Inverter power | 100–50000 W |
| `minimum_soc` | Minimum SOC limit | 0–100% |
| `maximum_soc` | Maximum SOC limit | 0–100% |

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

### `eos_ha.update_predictions`

Trigger EOS to recalculate all predictions (PV forecast, electricity prices, load forecast) without running a full optimization.

## E-Auto (Electric Vehicle) Support

Configure your EV in the setup wizard or options flow:

| Parameter | Description | Default |
|-----------|-------------|---------|
| Capacity | Battery capacity (kWh) | 60 kWh |
| Charge Power | Max charging power (W) | 11000 W |
| SOC Entity | HA sensor for current EV SOC | — |
| Efficiency | Charging efficiency (0–1) | 0.95 |

When enabled, the optimization includes the EV in the charge plan. The `ev_charge_plan` sensor shows the recommended charging schedule.

## Flexible Appliances

Add flexible home appliances (e.g. Brauchwasserwärmepumpe / hot water heat pump) that can be scheduled by the optimizer. Each appliance is defined with:

- Name
- Power consumption (W)
- Duration (hours)
- Allowed time window

The optimizer finds the cheapest time slot to run each appliance. Results are exposed in the `appliance_schedule` sensor.

## Feed-in Tariff

Configurable feed-in compensation rate (default: **0.082 EUR/kWh** — current German rate). Used by the optimizer to calculate the value of exporting surplus energy. Change it in the options flow under "Feed-in Tariff".

## Battery Storage Price Sensor

When battery sensor entities are configured (grid charge power, PV charge power, battery energy), the integration tracks the **weighted average cost of energy stored in the battery** in EUR/kWh.

- Grid-charged energy is valued at the current electricity price (adjusted for efficiency)
- PV-charged energy is valued at 0 EUR/kWh
- The sensor persists across restarts (uses HA's RestoreEntity)
- Useful for deciding whether to discharge (compare storage price vs. current grid price)

## 48-Hour Forecasts

All forecast sensors expose a `forecast` attribute containing the full 48-hour hourly forecast array. Use this in [ApexCharts Card](https://github.com/RomRider/apexcharts-card) or template sensors:

```yaml
type: custom:apexcharts-card
series:
  - entity: sensor.eos_energy_optimizer_pv_forecast
    data_generator: |
      return entity.attributes.forecast.map((val, idx) => {
        const d = new Date();
        d.setMinutes(0, 0, 0);
        d.setHours(d.getHours() + idx);
        return [d.getTime(), val];
      });
```

## Dashboard

A ready-to-use Lovelace dashboard is included at [`dashboards/eos-energy.yaml`](dashboards/eos-energy.yaml).

It includes:
- **Status card** — optimization status, current mode, energy plan, discharge, override, costs
- **PV Prognose** — 48h solar forecast (area chart, yellow)
- **Strompreis** — 48h electricity price in ct/kWh (line chart, red)
- **Batterie SOC** — 48h battery state of charge (area chart, blue)
- **Lade-/Entlade-Plan** — 48h AC+DC charge plan (stacked column chart, green)
- **Verbrauch** — 48h consumption forecast (area chart, purple)
- **Batterie-Parameter** — adjustable number entities

**Requirements:** Install [apexcharts-card](https://github.com/RomRider/apexcharts-card) via HACS → Frontend.

**To use:** Copy the YAML into a manual Lovelace dashboard or use HA's raw configuration editor.

## Diagnostics

Download diagnostics via **Settings → Devices & Services → EOS HA → ⋮ → Download Diagnostics**. Sensitive data (coordinates, server URL) is automatically redacted.

## License

MIT License — see [LICENSE](LICENSE) for details.
