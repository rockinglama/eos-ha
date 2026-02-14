# Requirements: EOS Connect HA Integration

**Defined:** 2026-02-14
**Core Value:** Reliably run the optimization cycle (collect data → optimize via EOS → expose results as entities) so users can make informed, automated energy decisions without running a separate container.

## v1 Requirements

Requirements for initial release. Each maps to roadmap phases.

### Integration Foundation

- [ ] **FOUND-01**: User can install integration via HACS (manifest.json, hacs.json, proper structure)
- [ ] **FOUND-02**: User can add integration via Config Flow (EOS server URL, location lat/lon for PV forecast)
- [ ] **FOUND-03**: User can configure input entities via Options Flow (price entity, SOC entity, consumption entity)
- [ ] **FOUND-04**: Integration validates EOS server reachability during Config Flow setup
- [ ] **FOUND-05**: Integration runs periodic optimization via DataUpdateCoordinator (configurable interval, default 5min)

### Data Input

- [ ] **INPUT-01**: Integration reads electricity price from user-selected HA entity (Tibber/Nordpool)
- [ ] **INPUT-02**: Integration reads battery SOC from user-selected HA entity
- [ ] **INPUT-03**: Integration reads consumption/load from user-selected HA entity
- [ ] **INPUT-04**: Integration fetches 48h PV forecast from Akkudoktor API using configured location
- [ ] **INPUT-05**: Integration builds EOS-format optimization request from collected data

### Optimization

- [ ] **OPT-01**: Integration sends optimization request to EOS server (async, non-blocking)
- [ ] **OPT-02**: Integration parses EOS optimization response and extracts control recommendations
- [ ] **OPT-03**: Integration handles EOS server errors gracefully (entities become unavailable, logs error)

### Output Entities

- [ ] **OUT-01**: Sensor: AC charge power recommendation (W, state_class: measurement)
- [ ] **OUT-02**: Sensor: DC charge power recommendation (W, state_class: measurement)
- [ ] **OUT-03**: Binary sensor: Discharge allowed (on/off)
- [ ] **OUT-04**: Sensor: Current recommended mode (Grid Charge / Avoid Discharge / Allow Discharge)
- [ ] **OUT-05**: Sensor: PV forecast with 48h hourly forecast as attributes
- [ ] **OUT-06**: Sensor: Price forecast with hourly prices as attributes
- [ ] **OUT-07**: 48h optimization schedule (calendar entity or sensor with schedule attributes)
- [ ] **OUT-08**: Sensor: Consumption forecast with forecast attributes

### Configuration Entities

- [ ] **CONF-01**: Number entity: Battery capacity (Wh)
- [ ] **CONF-02**: Number entity: Max charge power (W)
- [ ] **CONF-03**: Number entity: Min SOC (%)
- [ ] **CONF-04**: Number entity: Max SOC (%)

### Services

- [ ] **SVC-01**: Service eos_connect.set_override — set manual mode (force charge/discharge/auto) with duration
- [ ] **SVC-02**: Service eos_connect.optimize_now — trigger immediate optimization cycle

### Diagnostics

- [ ] **DIAG-01**: Diagnostics platform with sanitized config, last EOS request/response, server status

## v2 Requirements

Deferred to future release. Tracked but not in current roadmap.

### Additional Data Sources

- **SRC-01**: Multiple PV forecast sources (Solcast, Forecast.Solar, Open-Meteo)
- **SRC-02**: Multiple price sources (Nordpool, Octopus, EPEX Spot)

### Extended Features

- **EXT-01**: EVopt optimization backend support
- **EXT-02**: EVCC integration for EV charging optimization
- **EXT-03**: Multi-inverter / multi-battery support
- **EXT-04**: Cost savings sensor (daily/monthly € saved vs baseline)
- **EXT-05**: Optimization quality metrics (forecast accuracy, server response time)
- **EXT-06**: Live vs forecast comparison sensors

## Out of Scope

Explicitly excluded. Documented to prevent scope creep.

| Feature | Reason |
|---------|--------|
| Direct inverter control (Fronius API) | User builds automations; tight coupling to hardware is anti-pattern |
| Custom dashboard panel | HA native dashboard cards are sufficient; maintenance burden |
| YAML configuration | Deprecated HA pattern; Config Flow + Options Flow is standard |
| Built-in price APIs (Tibber, Stromlinging) | Price integrations are mature in HA; avoid duplicate API calls |
| Real-time (sub-minute) updates | EOS optimization is computationally expensive; 5min default sufficient |
| OpenHAB integration | HA only; OpenHAB users use the existing Docker container |
| Flask web server / REST API | Replaced by native HA entities and services |
| MQTT discovery | No longer needed; entities are native HA |

## Traceability

Which phases cover which requirements. Updated during roadmap creation.

| Requirement | Phase | Status |
|-------------|-------|--------|
| FOUND-01 | Phase 1, Phase 4 | Pending |
| FOUND-02 | Phase 1 | Pending |
| FOUND-03 | Phase 3 | Pending |
| FOUND-04 | Phase 1 | Pending |
| FOUND-05 | Phase 1 | Pending |
| INPUT-01 | Phase 1 | Pending |
| INPUT-02 | Phase 1 | Pending |
| INPUT-03 | Phase 1 | Pending |
| INPUT-04 | Phase 1 | Pending |
| INPUT-05 | Phase 1 | Pending |
| OPT-01 | Phase 1 | Pending |
| OPT-02 | Phase 1 | Pending |
| OPT-03 | Phase 1 | Pending |
| OUT-01 | Phase 2 | Pending |
| OUT-02 | Phase 2 | Pending |
| OUT-03 | Phase 2 | Pending |
| OUT-04 | Phase 2 | Pending |
| OUT-05 | Phase 2 | Pending |
| OUT-06 | Phase 2 | Pending |
| OUT-07 | Phase 2 | Pending |
| OUT-08 | Phase 2 | Pending |
| CONF-01 | Phase 3 | Pending |
| CONF-02 | Phase 3 | Pending |
| CONF-03 | Phase 3 | Pending |
| CONF-04 | Phase 3 | Pending |
| SVC-01 | Phase 3 | Pending |
| SVC-02 | Phase 3 | Pending |
| DIAG-01 | Phase 4 | Pending |

**Coverage:**
- v1 requirements: 28 total
- Mapped to phases: 28
- Unmapped: 0 ✓

---
*Requirements defined: 2026-02-14*
*Last updated: 2026-02-14 after roadmap creation with phase mappings*
