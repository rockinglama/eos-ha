<div align="center">
  <img src="icon.jpg" alt="EOS-HA Logo" width="200"/>

  # EOS-HA

  [![HACS Validation](https://github.com/rockinglama/eos-ha/actions/workflows/validate.yml/badge.svg)](https://github.com/rockinglama/eos-ha/actions/workflows/validate.yml)
  [![Add to HACS](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=rockinglama&repository=eos-ha&category=integration)

  A Home Assistant custom integration for [Akkudoktor EOS](https://github.com/Akkudoktor-EOS/EOS) energy optimization.
</div>

## What It Does

EOS-HA uses the **EOS native Home Assistant Adapter** for bidirectional data exchange:

1. **Configures** your EOS server at startup — battery, inverter, PV arrays, price provider, devices, and adapter entity mappings
2. **EOS reads** entity states directly from Home Assistant — battery SOC, consumption, energy meters
3. **EOS runs** automatic optimization at configurable intervals (default: every hour)
4. **EOS writes** optimization results back as HA entities (`sensor.eos_*`)
5. **EOS-HA wraps** those results with proper entity IDs, device grouping, translations, and extra features (SG-Ready, battery price tracking, blueprints)

You keep full control — EOS-HA provides recommendations as sensor entities. You decide how to act on them with your own automations.

## Requirements

- Home Assistant 2024.1+
- A running [Akkudoktor EOS](https://github.com/Akkudoktor-EOS/EOS) server (addon or standalone)
- A battery SOC sensor
- A consumption/load sensor
- An electricity price sensor (only if using "External" price source)

> **Tip:** For the best experience, run EOS as a Home Assistant addon — the HA Adapter provides direct entity access for seamless integration.

## Installation

### HACS (Recommended)

1. Click the badge above, or go to **HACS → Integrations → ⋮ → Custom repositories**
2. Add `https://github.com/rockinglama/eos-ha` as an Integration
3. Search for **EOS HA** and install
4. Restart Home Assistant

### Manual

1. Copy `custom_components/eos_ha/` to your HA `config/custom_components/` directory
2. Restart Home Assistant

## Dashboard

![EOS Dashboard](docs/assets/images/dashboard.png)

## Removal

1. Go to **Settings → Devices & Services → EOS HA**
2. Click **⋮ → Delete**
3. Restart Home Assistant
4. (Optional) Uninstall via HACS or remove `custom_components/eos_ha/`

## Configuration

Add the integration via **Settings → Devices & Services → + Add Integration → EOS HA**.

### Config Flow

| Step | What You Configure |
|------|--------------------|
| **EOS Server** | URL of your EOS server (auto-detected if running as addon) |
| **Entities** | Battery SOC sensor, consumption sensor, electricity price sensor (if external), temperature sensor |
| **Battery** | Capacity (kWh), max charge power (W), inverter power (W), SOC limits (%) |
| **PV Arrays** | Solar arrays with azimuth, tilt, peak power, inverter power, efficiency |
| **Price Source** | Akkudoktor, EnergyCharts, or External (Tibber, ENTSO-E, etc.) |
| **EV** *(optional)* | Electric vehicle — capacity, charge power, SOC entity, efficiency |
| **Appliances** *(optional)* | Flexible loads with time windows (e.g. Brauchwasserwärmepumpe) |
| **Energy Meters** *(optional)* | Load, grid import/export, PV production energy meters for forecast correction |
| **Battery Sensors** *(optional)* | Entities for battery storage price tracking |
| **SG-Ready** *(optional)* | Heat pump relay switches for SG-Ready control |
| **Feed-in Tariff** | Feed-in compensation rate (Einspeisevergütung, default 0.082 €/kWh) |

### Options Flow

All parameters can be changed at runtime via **Settings → Devices & Services → EOS HA → Configure**.

### EOS Addon Auto-Detection

If EOS runs as a Home Assistant addon, the integration detects it via the Supervisor API and pre-fills the server URL.

## EOS HA Adapter

The integration configures the [EOS HA Adapter](https://akkudoktor-eos.readthedocs.io/en/latest/akkudoktoreos/adapter/adapterhomeassistant.html) at startup:

**EOS reads from HA:**
- Battery SOC (via `device_measurement_entity_ids`)
- Energy meter readings: load, grid import/export, PV production (for forecast correction)

**EOS writes to HA:**
- `sensor.eos_battery1` — battery operation mode and instructions
- `sensor.eos_genetic_ac_charge_factor` — AC charge schedule
- `sensor.eos_genetic_dc_charge_factor` — DC charge schedule
- `sensor.eos_genetic_discharge_allowed_factor` — discharge allowed
- `sensor.eos_battery1_soc_factor` — SOC forecast
- `sensor.eos_costs_amt` / `sensor.eos_revenue_amt` — costs and revenue
- `sensor.eos_grid_consumption_energy_wh` / `sensor.eos_grid_feedin_energy_wh`
- Plus battery operation mode entities for all supported modes

EOS-HA wraps these with proper `unique_id`, device grouping under "EOS", and translations.

## Price Sources

| Source | Description |
|--------|-------------|
| **Akkudoktor** (default) | Built-in price forecast via EOS |
| **EnergyCharts** | EOS fetches from energy-charts.info (configurable bidding zone, default DE-LU) |
| **External** | Any HA sensor (Tibber, ENTSO-E, Awattar) — pushed to EOS via `ElecPriceImport` provider |

## Entities

### Sensors

| Entity | Description |
|--------|-------------|
| `optimization_status` | Optimization state: `optimized`, `failed`, `unknown` |
| `ac_charge_power` | AC charge power (W); 48h forecast in attributes |
| `dc_charge_power` | DC charge power (W); 48h forecast in attributes |
| `current_mode` | Current mode: `Grid Charge`, `Allow Discharge`, `Avoid Discharge`, or override |
| `pv_forecast` | PV forecast (W); 48h forecast in attributes |
| `price_forecast` | Electricity price (EUR/Wh); 48h forecast with `price_below_average`, `cheapest_hours` |
| `consumption_forecast` | Consumption forecast (W); 48h forecast in attributes |
| `battery_soc_forecast` | Battery SOC (%); 48h forecast in attributes |
| `override_status` | Active manual override (`charge`, `discharge`, `none`) |
| `total_cost` | Total optimized cost (EUR) |
| `energy_plan` | Current operation mode from energy plan |
| `resource_status` | Battery resource availability |
| `ev_charge_plan` | EV charge plan (`active`/`inactive`) |
| `appliance_schedule` | Scheduled appliances count and details |
| `battery_storage_price` | Weighted avg cost of stored energy (EUR/kWh) |
| `sg_ready_mode` | Recommended SG-Ready mode (1–4) |

### Binary Sensors

| Entity | Description |
|--------|-------------|
| `discharge_allowed` | Whether battery discharge is allowed |

### Number Entities

Adjustable at runtime:

| Entity | Range |
|--------|-------|
| `battery_capacity` | 0.1–100 kWh |
| `max_charge_power` | 100–50000 W |
| `inverter_power` | 100–50000 W |
| `minimum_soc` | 0–100% |
| `maximum_soc` | 0–100% |

### Switch

| Entity | Description |
|--------|-------------|
| `sg_ready_auto` | Enable/disable automatic SG-Ready relay control |

### Button

| Entity | Description |
|--------|-------------|
| `reset_battery_price` | Reset battery storage price tracking to zero |

## Services

### `eos_ha.optimize_now`

Trigger an immediate optimization (updates predictions then refreshes).

### `eos_ha.set_override`

Override the optimization mode:

```yaml
service: eos_ha.set_override
data:
  mode: charge  # charge | discharge | auto
  duration: 120  # minutes (1–1440)
```

### `eos_ha.update_predictions`

Trigger EOS to recalculate all predictions without full optimization.

### `eos_ha.set_sg_ready_mode`

Override SG-Ready mode:

```yaml
service: eos_ha.set_sg_ready_mode
data:
  mode: 3  # 1=Lock, 2=Normal, 3=Recommend, 4=Force
  duration: 60  # minutes (0=permanent)
```

### `eos_ha.reset_battery_price`

Reset battery storage price tracking to zero.

## SG-Ready Heat Pump

Control SG-Ready heat pumps via two relay switches:

| Mode | Contact 1 | Contact 2 | Meaning |
|------|-----------|-----------|---------|
| 1 — Lock | ON | OFF | Block heat pump (expensive electricity) |
| 2 — Normal | OFF | OFF | Normal operation |
| 3 — Recommend | OFF | ON | Recommend run (PV surplus / cheap power) |
| 4 — Force | ON | ON | Force run (significant PV surplus, battery full) |

The **SG-Ready Mode sensor** recommends a mode based on:
- PV surplus vs. consumption
- Current vs. average electricity price
- Battery SOC level

The **SG-Ready Auto switch** automatically controls your relay entities based on the recommended mode.

## Flexible Appliances (Flexible Lasten)

Add appliances like a Brauchwasserwärmepumpe that the optimizer schedules at the cheapest time:

| Parameter | Description | Example |
|-----------|-------------|---------|
| Name | Appliance name | Brauchwasserwärmepumpe |
| Energy (Wh) | Total energy per run | 2000 Wh |
| Duration (h) | Run duration | 3 hours |
| Earliest Start | Earliest allowed start time | 06:00 |
| Latest End | Latest allowed end time | 22:00 |

Multiple appliances supported, each with individual time windows. Results in the `appliance_schedule` sensor.

## Temperature Entity

Configure a weather entity or temperature sensor for temperature-aware optimization. Falls back to 15°C if not configured. Supports:
- Weather entities (uses forecast attribute for 48h)
- Temperature sensors (uses current value for all 48h)

## Battery Storage Price Sensor

Tracks the **weighted average cost of energy stored in the battery** (EUR/kWh):
- Grid-charged energy valued at current electricity price (adjusted for efficiency)
- PV-charged energy valued at 0 EUR/kWh
- Persists across restarts (RestoreEntity)
- Reset via button or service

## Automation Blueprints

Four ready-to-use blueprints included in `blueprints/`:

| Blueprint | Description |
|-----------|-------------|
| `charge_battery_cheap` | Charge battery during cheapest hours |
| `sg_ready_pv_surplus` | Activate SG-Ready mode 3/4 on PV surplus |
| `notify_cheap_power` | Notify when electricity is cheap |
| `notify_negative_price` | Notify on negative electricity prices |

## 48-Hour Forecasts

All forecast sensors expose a `forecast` attribute with the full 48-hour array. Example with [ApexCharts Card](https://github.com/RomRider/apexcharts-card):

```yaml
type: custom:apexcharts-card
series:
  - entity: sensor.eos_pv_forecast
    data_generator: |
      return entity.attributes.forecast.map((val, idx) => {
        const d = new Date();
        d.setMinutes(0, 0, 0);
        d.setHours(d.getHours() + idx);
        return [d.getTime(), val];
      });
```

## Dashboard

A ready-to-use dashboard is included at [`dashboards/eos-energy.yaml`](dashboards/eos-energy.yaml) with status, PV forecast, electricity price, battery SOC, charge plan, consumption, SG-Ready, and battery price cards.

**Requires:** [apexcharts-card](https://github.com/RomRider/apexcharts-card) via HACS → Frontend.

## Translations

Full translations available:
- 🇬🇧 English
- 🇩🇪 German (Deutsch)

## Diagnostics

Download via **Settings → Devices & Services → EOS HA → ⋮ → Download Diagnostics**. Sensitive data is automatically redacted.

## License

MIT License — see [LICENSE](LICENSE) for details.
