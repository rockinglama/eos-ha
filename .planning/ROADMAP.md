# Roadmap: EOS Connect HA Integration

## Overview

Transform EOS_connect from a standalone Docker container into a native Home Assistant custom integration. The journey starts with establishing the HA integration foundation and async architecture, exposes optimization results as HA entities, adds runtime configuration and manual control capabilities, and finishes with HACS-ready packaging for community distribution.

## Phases

**Phase Numbering:**
- Integer phases (1, 2, 3, 4): Planned milestone work
- Decimal phases (2.1, 2.2): Urgent insertions (marked with INSERTED)

Decimal phases appear between their surrounding integers in numeric order.

- [ ] **Phase 1: Foundation & Data Flow** - HACS structure, Config Flow, DataUpdateCoordinator, EOS optimization cycle
- [ ] **Phase 2: Output Entities** - Sensors and binary sensors exposing optimization results
- [ ] **Phase 3: Configuration & Control** - Options Flow, number entities, manual override services
- [ ] **Phase 4: Diagnostics & HACS Publishing** - Diagnostics platform, HACS packaging, documentation

## Phase Details

### Phase 1: Foundation & Data Flow
**Goal**: Integration appears in HA UI, connects to EOS server, runs periodic optimization cycle, and processes data flow end-to-end
**Depends on**: Nothing (first phase)
**Requirements**: FOUND-01, FOUND-02, FOUND-04, FOUND-05, INPUT-01, INPUT-02, INPUT-03, INPUT-04, INPUT-05, OPT-01, OPT-02, OPT-03
**Success Criteria** (what must be TRUE):
  1. User can install integration via HACS and see it in Add Integration UI
  2. User can add integration via Config Flow by providing EOS server URL and location coordinates
  3. Integration validates EOS server is reachable during setup and shows clear error if not
  4. Integration runs periodic optimization every 5 minutes (configurable interval)
  5. Integration reads data from user-selected HA entities (price, SOC, consumption) and Akkudoktor API
  6. Integration sends optimization request to EOS server and receives valid response
  7. Integration handles EOS server errors gracefully (logs error, retries on next cycle)
**Plans**: TBD

Plans:
- [ ] TBD during phase planning

### Phase 2: Output Entities
**Goal**: Optimization results are visible as HA entities that users can consume in automations and dashboards
**Depends on**: Phase 1
**Requirements**: OUT-01, OUT-02, OUT-03, OUT-04, OUT-05, OUT-06, OUT-07, OUT-08
**Success Criteria** (what must be TRUE):
  1. User sees AC charge power sensor with current recommendation in watts
  2. User sees DC charge power sensor with current recommendation in watts
  3. User sees binary sensor for discharge allowed (on/off) that can trigger automations
  4. User sees current mode sensor showing Grid Charge, Avoid Discharge, or Allow Discharge
  5. User sees PV forecast sensor with 48-hour hourly forecast in attributes
  6. User sees price forecast sensor with hourly prices in attributes
  7. User sees consumption forecast sensor with forecast data in attributes
  8. User sees 48-hour optimization schedule (calendar entity or sensor with schedule attributes)
  9. All power sensors are compatible with Energy Dashboard (correct device_class and state_class)
**Plans**: TBD

Plans:
- [ ] TBD during phase planning

### Phase 3: Configuration & Control
**Goal**: Users can configure battery parameters at runtime and manually override automatic optimization when needed
**Depends on**: Phase 2
**Requirements**: FOUND-03, CONF-01, CONF-02, CONF-03, CONF-04, SVC-01, SVC-02
**Success Criteria** (what must be TRUE):
  1. User can access Options Flow to change input entities without deleting integration
  2. User can change battery capacity via number entity and see it reflected in next optimization
  3. User can change max charge power via number entity and see it reflected in next optimization
  4. User can change min/max SOC limits via number entities and see them reflected in next optimization
  5. User can call eos_connect.set_override service to force specific mode (charge/discharge/auto) with duration
  6. User can call eos_connect.optimize_now service to trigger immediate optimization cycle
  7. Options Flow changes trigger coordinator update without requiring integration reload
**Plans**: TBD

Plans:
- [ ] TBD during phase planning

### Phase 4: Diagnostics & HACS Publishing
**Goal**: Integration is production-ready, debuggable, and available for community installation via HACS
**Depends on**: Phase 3
**Requirements**: DIAG-01, FOUND-01 (HACS packaging)
**Success Criteria** (what must be TRUE):
  1. User can download diagnostics file with sanitized config and last EOS request/response
  2. Integration passes HACS validation (proper manifest.json, hacs.json, directory structure)
  3. User can find installation instructions in README with examples
  4. User can see example automations for discharge control and override scenarios
  5. Integration repository has GitHub release with version tag
**Plans**: TBD

Plans:
- [ ] TBD during phase planning

## Progress

**Execution Order:**
Phases execute in numeric order: 1 → 2 → 3 → 4

| Phase | Plans Complete | Status | Completed |
|-------|----------------|--------|-----------|
| 1. Foundation & Data Flow | 0/TBD | Not started | - |
| 2. Output Entities | 0/TBD | Not started | - |
| 3. Configuration & Control | 0/TBD | Not started | - |
| 4. Diagnostics & HACS Publishing | 0/TBD | Not started | - |

---
*Roadmap created: 2026-02-14*
*Last updated: 2026-02-14*
