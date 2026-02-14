# Feature Landscape: Home Assistant Energy Optimization Integrations

**Domain:** Home Assistant Energy Optimization Integrations
**Researched:** 2026-02-14
**Confidence:** HIGH

## Feature Landscape

### Table Stakes (Users Expect These)

Features users assume exist. Missing these = product feels incomplete.

| Feature | Why Expected | Complexity | Notes |
|---------|--------------|------------|-------|
| **Config Flow Setup** | Standard HA pattern; users expect UI-based config | Medium | Required: server URL, location, entity selectors. YAML config is deprecated pattern. |
| **Options Flow** | Users expect to reconfigure without deleting integration | Medium | Battery params, entity mapping, optimization settings. Separate from initial config. |
| **Price Forecast Sensor** | Energy optimization requires future prices | Low | Must expose `attributes` with hourly price array (24-48h). Tibber/Nordpool expose `max_price`/`min_price` attrs. |
| **Current Recommendation Sensors** | Users need "what should I do NOW" | Low | AC charge power (W), DC charge power (W), current mode (Grid Charge/Avoid Discharge/etc). |
| **Battery SOC Integration** | Core input for optimization | Low | Read from user-selected HA entity. Must handle both % (0-100) and Wh formats. |
| **Energy Dashboard Compatible** | Users expect integration with HA Energy Dashboard | Medium | Sensors need `device_class: energy/power`, `state_class: total_increasing/measurement`, units in kWh/W. |
| **Periodic Optimization** | Must refresh automatically | Medium | DataUpdateCoordinator pattern. Configurable refresh interval (default: 5min). Don't hammer EOS server. |
| **PV Forecast Sensor** | Solar optimization requires future production | Medium | Fetch from Akkudoktor API. Expose hourly forecast as attributes (48h). Device class: power. |
| **Discharge Control Binary Sensor** | Enable/disable discharge based on prices | Low | Common pattern: `binary_sensor.discharge_allowed` (on = allow, off = block). Used in automations. |
| **Error Handling / Diagnostics** | Integration quality scale requirement | Medium | Implement diagnostics platform. Expose EOS server status, last successful optimization timestamp, error states. |
| **HACS Compatibility** | Community distribution expectation | Low | `manifest.json` with quality_scale, `hacs.json`, proper directory structure, GitHub releases. |

### Differentiators (Competitive Advantage)

Features that set the product apart. Not expected, but valued.

| Feature | Value Proposition | Complexity | Notes |
|---------|-------------------|------------|-------|
| **48h Schedule Visualization** | Users want to see the full optimization plan, not just current recommendation | High | Expose as sensor attributes (JSON array) OR calendar entity (better UX). Predbat does this well. EMHASS exposes plan but less user-friendly. |
| **Manual Override Service** | Users need to override optimization temporarily (guests coming, weather event) | Medium | Service: `eos_ha.set_override` with mode (force charge/discharge/auto) + duration. Nordpool + battery integrations don't offer this. |
| **Live vs Forecast Comparison** | Show how actual vs predicted diverges (builds trust) | Medium | Separate sensors: `actual_consumption_today`, `forecast_consumption_today`. Helps users understand optimization quality. |
| **Battery Parameter Number Entities** | Allow automation-driven parameter changes (vacation mode, winter/summer profiles) | Medium | Capacity, max charge/discharge power, efficiency, min/max SOC. Most integrations hardcode these in config. |
| **Multi-Inverter Support Pattern** | Users may have multiple batteries/inverters | High | Support multiple config entries? Or multiple battery blocks in single entry? Defer to v2 but architect for it. |
| **Cost Savings Sensor** | Gamification / ROI visibility | Medium | Calculate saved € based on actual vs grid-only scenario. Updates daily. Tibber shows savings, Powerwall doesn't. |
| **Optimization Quality Metrics** | Transparency into optimization health | Low | Expose: forecast accuracy (MAE), EOS server response time, last optimization status (success/partial/failed). |
| **Flexible Forecast Attributes** | Better than competitors' attribute structure | Low | Use HA's new `weather.get_forecasts` pattern: service returning forecast data, not just attributes. Easier for UI cards. |

### Anti-Features (Commonly Requested, Often Problematic)

Features that seem good but create problems.

| Feature | Why Requested | Why Problematic | Alternative |
|---------|---------------|-----------------|-------------|
| **Direct Inverter Control** | "Make it work out of box" | Creates tight coupling to specific hardware; users want flexibility | Expose clear recommendation sensors. User builds automations. Document common patterns. |
| **Built-in Price APIs** | "Don't make me install Tibber/Nordpool integration" | Duplicate effort; price integrations are mature; API key management complexity | Require existing HA price entity. Users already have Tibber/Nordpool/Octopus. |
| **Multiple PV Forecast Sources** | "Support Solcast, Forecast.Solar, etc" | API key sprawl; each has different data models; increases support burden | Akkudoktor API only for v1. Well-tested, no API key. Add others in v2 if demanded. |
| **Real-Time (Sub-Minute) Updates** | "Faster = better" | EOS optimization is computationally expensive; sub-5min polling wasteful; battery control is slow-changing | 5-minute default refresh. Expose manual "optimize now" service for edge cases. |
| **YAML Configuration** | "I want to see my config" | HA moved away from YAML for integrations; Config Flow is standard; YAML import is legacy anti-pattern | Config Flow + Options Flow only. Export diagnostics as JSON if users want to see config. |
| **Custom Dashboard Panel** | "Embedded UI is cooler" | Maintenance burden; HA dashboard cards are powerful; users customize anyway | Provide example dashboard YAML. Use standard HA cards (ApexCharts, entities card, etc). |
| **Everything Configurable** | "Give me all the knobs" | Choice paralysis; most users want sane defaults | Opinionated defaults. Hide advanced options in Options Flow. Progressive disclosure pattern. |

## Feature Dependencies

```
Config Flow (initial setup)
    └──requires──> EOS Server reachability check
                       └──requires──> aiohttp for async HTTP

Options Flow
    └──requires──> Config Flow (must be set up first)
    └──enhances──> Battery Parameter Number Entities

DataUpdateCoordinator (optimization cycle)
    ├──requires──> Config Flow data (server URL, location)
    ├──requires──> Price Entity (read from HA state)
    ├──requires──> SOC Entity (read from HA state)
    ├──requires──> Akkudoktor PV Forecast API
    └──produces──> All sensor entities

Sensor Entities
    └──requires──> DataUpdateCoordinator success
    └──enables──> User automations

Binary Sensor (discharge allowed)
    └──requires──> Optimization result from coordinator
    └──enables──> Automation triggers

Number Entities (battery params)
    ├──independent──> Can be set before optimization
    └──feeds──> DataUpdateCoordinator (used in EOS request)

Override Service
    ├──requires──> Valid config entry
    └──conflicts──> Automatic optimization (temporarily)

Energy Dashboard Integration
    ├──requires──> Sensors with proper device_class + state_class
    └──optional──> Not blocking core functionality

Diagnostics
    └──requires──> Config entry data
    └──independent──> Works even if optimization fails

48h Schedule (Calendar or Attributes)
    └──requires──> Successful optimization response
    └──enhances──> Schedule visualization in dashboard
```

### Dependency Notes

- **Config Flow must validate EOS server** before completing setup — don't let users proceed with unreachable server
- **Options Flow needs entity selectors** to be dynamic (filter by device_class: power/energy for consumption entities)
- **DataUpdateCoordinator is the heart** — all output entities depend on it; failure here cascades
- **Number entities vs Options Flow**: Battery params can be Options Flow fields OR Number entities. Number entities enable automation-driven changes. More powerful but more entities.
- **Override Service conflicts with automatic mode**: Need state machine to track "manual override active" and resume automatic after timeout
- **Energy Dashboard integration is optional**: Don't block core functionality if user doesn't use Energy Dashboard

## MVP Definition

### Launch With (v1)

Minimum viable product — what's needed to validate the concept.

- [x] **Config Flow with EOS server setup** — URL, port, location (lat/lon for PV forecast)
- [x] **Options Flow for entity selection** — price entity, SOC entity, consumption entity selectors
- [x] **Price Forecast Sensor** — reads from user-selected HA entity (Tibber/Nordpool), exposes with attributes
- [x] **PV Forecast Sensor** — fetches from Akkudoktor API, exposes hourly forecast (48h) as attributes
- [x] **Battery SOC Input** — reads from user-selected entity
- [x] **Consumption Input** — reads from user-selected entity (or use historical stats as fallback)
- [x] **Current Charge Recommendation Sensors** — AC power (W), DC power (W), mode (text sensor)
- [x] **Discharge Allowed Binary Sensor** — on/off for automation triggers
- [x] **DataUpdateCoordinator** — periodic optimization (5min default), handles EOS server communication
- [x] **Basic Error Handling** — log failures, set entities to unavailable on error, expose last update timestamp
- [x] **HACS Compatibility** — manifest.json, hacs.json, proper structure, GitHub release workflow

**Why these are essential:**
- Config/Options Flow: Standard HA pattern, expected by users
- Forecast sensors: Can't optimize without future data
- Current recommendations: Users need "what to do now" immediately
- Discharge binary sensor: Most common automation use case
- DataUpdateCoordinator: Orchestrates everything; without it, nothing works
- HACS: Expected distribution method for custom integrations

### Add After Validation (v1.x)

Features to add once core is working and users provide feedback.

- [ ] **48h Schedule Visualization** — expose optimization plan as calendar entity or enhanced attributes (trigger: users request "I want to see the full plan")
- [ ] **Battery Parameter Number Entities** — capacity, max charge/discharge power, efficiency (trigger: users want to change settings without going to Options Flow)
- [ ] **Manual Override Service** — `eos_ha.set_override` with mode + duration (trigger: "I need to force charge before a storm")
- [ ] **Cost Savings Sensor** — daily/monthly € saved vs baseline (trigger: users want ROI visibility)
- [ ] **Diagnostics Platform** — downloadable diagnostics file with sanitized config + last EOS response (trigger: GitHub issues need debug info)
- [ ] **Optimization Quality Metrics** — forecast accuracy, last optimization status, server response time (trigger: "Is optimization working well?")
- [ ] **Consumption Forecast Sensor** — expose predicted load for next 48h (trigger: users building advanced dashboards)

**Triggers for adding:**
- v1 ships, users start automations
- GitHub issues reveal common pain points
- Users request specific features in discussions

### Future Consideration (v2+)

Features to defer until product-market fit is established.

- [ ] **Multiple Price Sources** — Nordpool, Octopus Energy, EPEX Spot, etc (why defer: complexity, user already has price entity)
- [ ] **Multiple PV Forecast Sources** — Solcast, Forecast.Solar, Open-Meteo (why defer: API key management, Akkudoktor sufficient)
- [ ] **EVopt Backend Support** — alternative to EOS Server (why defer: adds testing complexity, EOS is sufficient for v1)
- [ ] **EVCC Integration** — EV charge optimization (why defer: separate domain, smaller user base)
- [ ] **Multi-Inverter / Multi-Battery** — support multiple batteries in one instance (why defer: complex UI, rare use case)
- [ ] **Predbat Compatibility Mode** — mimic Predbat's entity structure for easy migration (why defer: only if Predbat users request it)
- [ ] **Weather-Based Adjustments** — consume HA weather entity for temperature/cloud forecasts (why defer: Akkudoktor PV API already includes weather)
- [ ] **Historical Data Export** — export optimization history to CSV/JSON (why defer: users can use HA's built-in history)

## Feature Prioritization Matrix

| Feature | User Value | Implementation Cost | Priority |
|---------|------------|---------------------|----------|
| Config Flow + Options Flow | HIGH | MEDIUM | P1 |
| DataUpdateCoordinator (optimization cycle) | HIGH | MEDIUM | P1 |
| Current Recommendation Sensors | HIGH | LOW | P1 |
| Price Forecast Sensor | HIGH | LOW | P1 |
| PV Forecast Sensor | HIGH | MEDIUM | P1 |
| Discharge Binary Sensor | HIGH | LOW | P1 |
| HACS Compatibility | HIGH | LOW | P1 |
| Basic Error Handling | HIGH | LOW | P1 |
| Battery Parameter Number Entities | MEDIUM | LOW | P2 |
| 48h Schedule Visualization | HIGH | HIGH | P2 |
| Manual Override Service | MEDIUM | MEDIUM | P2 |
| Diagnostics Platform | MEDIUM | LOW | P2 |
| Cost Savings Sensor | MEDIUM | MEDIUM | P2 |
| Optimization Quality Metrics | LOW | LOW | P2 |
| Consumption Forecast Sensor | LOW | LOW | P2 |
| Multiple PV Forecast Sources | LOW | HIGH | P3 |
| EVopt Backend Support | LOW | MEDIUM | P3 |
| EVCC Integration | LOW | HIGH | P3 |
| Multi-Battery Support | LOW | HIGH | P3 |

**Priority key:**
- P1: Must have for launch (blocks MVP)
- P2: Should have, add when possible (enhances UX, requested by users)
- P3: Nice to have, future consideration (niche use cases, high complexity)

## Competitor Feature Analysis

| Feature | Tibber | Nordpool | Forecast.Solar | Powerwall | EMHASS | Predbat | Our Approach |
|---------|--------|----------|----------------|-----------|--------|---------|--------------|
| **Price Forecast** | ✓ 24h | ✓ 24h | ✗ | ✗ | Reads from entity | Reads from entity | **Read from existing HA entity** (Tibber/Nordpool) |
| **PV Forecast** | ✗ | ✗ | ✓ (today+tomorrow) | ✗ | Multiple sources | Solcast | **Akkudoktor API (48h)** |
| **Battery Optimization** | ✗ | ✗ | ✗ | ✓ (limited) | ✓ Full | ✓ Full | **EOS Server (full)** |
| **Current Recommendations** | ✗ | ✗ | ✗ | ✗ | ✓ (deferrable loads) | ✓ (charge/discharge) | **✓ AC/DC power + mode** |
| **48h Schedule** | ✗ | ✗ | ✗ | ✗ | ✓ (attributes) | ✓ (plan entities) | **✓ Calendar or attributes** (v1.x) |
| **Manual Override** | ✗ | ✗ | ✗ | ✓ (modes) | ✗ | ✓ (service) | **✓ Service with timeout** (v1.x) |
| **Config Flow** | ✓ | ✓ | ✓ | ✓ | ✗ (YAML) | ✗ (YAML) | **✓ Config + Options** |
| **Number Entities (Params)** | ✗ | ✗ | ✗ | ✗ | ✗ (YAML only) | ✗ (YAML only) | **✓ Battery params** (v1.x) |
| **Diagnostics** | ✓ | ✓ | ✓ | ✓ | ✗ | ✗ | **✓ Platform** (v1.x) |
| **Energy Dashboard** | ✓ | ✓ | ✓ | ✓ | ✗ | ✗ | **✓ Compatible sensors** |
| **Cost Savings** | ✓ | ✗ | ✗ | ✗ | ✗ | ✓ (computed) | **✓ Sensor** (v1.x) |

**Key Insights:**
- **Tibber/Nordpool**: Price specialists. We read from them, don't compete.
- **Forecast.Solar**: PV specialist. Limited (today+tomorrow). Akkudoktor gives 48h.
- **Powerwall**: Hardware-specific. Limited optimization. No visibility into schedule.
- **EMHASS**: Powerful but YAML-only config (no Config Flow). Complex setup. We improve UX.
- **Predbat**: Most similar competitor. Mature, feature-rich. YAML-only. Our advantage: Config Flow + cleaner UX + EOS backend.

**Our Differentiation:**
1. **Config Flow + Options Flow** — easier setup than EMHASS/Predbat
2. **Number entities for battery params** — dynamic configuration
3. **EOS Server backend** — leverages mature, actively developed optimizer
4. **Clean entity structure** — opinionated, not sprawling like Predbat's 100+ entities

## Entity Type Patterns (From Research)

Based on official HA integrations and best practices:

### Sensor Entities
- **Device Class**: `energy`, `power`, `battery`, `monetary` (for prices)
- **State Class**: `total_increasing` (cumulative energy), `measurement` (instantaneous power/price)
- **Units**: W, kW, kWh, €/kWh, %
- **Attributes**: Forecast data as JSON array (hourly slots with `datetime`, `value`)
- **Example**: `sensor.eos_ac_charge_power` (W, state_class: measurement)

### Binary Sensors
- **Device Class**: `battery_charging`, `power` (custom), or none
- **States**: on/off
- **Example**: `binary_sensor.eos_discharge_allowed` (on = allow discharge)

### Number Entities
- **Mode**: `box` (slider) or `slider`
- **Min/Max/Step**: Define valid ranges
- **Units**: Wh, W, % (efficiency)
- **Example**: `number.eos_battery_capacity` (min: 1000, max: 100000, step: 100, unit: Wh)

### Services
- **Schema**: Define with `vol.Schema` in `services.yaml`
- **Target**: Entity-level (acts on specific integration instance)
- **Response**: Optional (for get_forecasts pattern)
- **Example**: `eos_ha.set_override` with `mode`, `duration_minutes`

### Calendar Entity (Optional for Schedule)
- **Events**: Charge/discharge blocks with start/end times
- **Attributes**: `message` (mode), `start_time`, `end_time`
- **Better UX** than JSON attributes for schedule visualization

## Sources

### Official Documentation (HIGH Confidence)
- [Home Assistant Energy Dashboard](https://www.home-assistant.io/docs/energy/)
- [Sensor Entity Developer Docs](https://developers.home-assistant.io/docs/core/entity/sensor/)
- [Config Flow Developer Docs](https://developers.home-assistant.io/docs/config_entries_config_flow_handler/)
- [Integration Service Actions](https://developers.home-assistant.io/docs/dev_101_services/)
- [Integration Quality Scale](https://www.home-assistant.io/docs/quality_scale/)
- [Binary Sensor Entity](https://developers.home-assistant.io/docs/core/entity/binary-sensor/)
- [Implements Diagnostics](https://developers.home-assistant.io/docs/core/integration-quality-scale/rules/diagnostics/)

### Official Integrations (HIGH Confidence)
- [Forecast.Solar Integration](https://www.home-assistant.io/integrations/forecast_solar/)
- [Nord Pool Integration](https://www.home-assistant.io/integrations/nordpool/)
- [Tibber Integration](https://www.home-assistant.io/integrations/tibber/)
- [Tesla Powerwall Integration](https://www.home-assistant.io/integrations/powerwall/)

### Community Integrations (MEDIUM Confidence)
- [EMHASS Documentation](https://emhass.readthedocs.io/)
- [EMHASS GitHub](https://github.com/davidusb-geek/emhass)
- [Predbat Documentation](https://springfall2008.github.io/batpred/)
- [Predbat GitHub](https://github.com/springfall2008/batpred)

### HACS & Distribution (HIGH Confidence)
- [HACS Integration Requirements](https://www.hacs.xyz/docs/publish/integration/)
- [Integration Manifest Docs](https://developers.home-assistant.io/docs/creating_integration_manifest/)

### Community Discussions (MEDIUM Confidence)
- [HA Community: EMHASS Thread](https://community.home-assistant.io/t/emhass-an-energy-management-for-home-assistant/338126)
- [HA Community: Battery Automation Patterns](https://community.home-assistant.io/t/automation-of-battery-discharge/878641)
- [HA Community: Config Flow Best Practices](https://community.home-assistant.io/t/configflowhandler-and-optionsflowhandler-managing-the-same-parameter/365582)

---
*Feature research for: EOS HA HA Integration*
*Researched: 2026-02-14*
