# EOS HA HA Integration

## What This Is

A HACS-compatible Home Assistant custom integration that replaces the standalone eos-ha Docker container. It takes energy data from existing HA entities (electricity prices, battery SOC, consumption) and the Akkudoktor PV forecast API, sends it to an EOS optimization server, and exposes the optimization results as HA entities — enabling users to build their own automations for inverter control.

## Core Value

The integration must reliably run the optimization cycle (collect data → optimize via EOS → expose results as entities) so users can make informed, automated energy decisions without running a separate container.

## Requirements

### Validated

- ✓ Optimization logic against EOS Server — existing, proven in eos-ha
- ✓ Akkudoktor PV forecast API integration — existing
- ✓ EOS request/response format handling — existing
- ✓ Periodic optimization scheduling — existing pattern
- ✓ Dynamic battery charge limit calculation — existing

### Active

- [ ] HA custom integration with Config Flow + Options Flow
- [ ] Input: Electricity price from configurable HA entity (Tibber integration)
- [ ] Input: Battery SOC from configurable HA entity
- [ ] Input: Consumption/load from configurable HA entity
- [ ] Input: PV forecast via Akkudoktor API (built-in, location configurable)
- [ ] Input: Battery parameters as Number entities (capacity, max charge power, min/max SOC)
- [ ] Processing: Periodic optimization cycle against EOS Server
- [ ] Output: AC charge power recommendation sensor
- [ ] Output: DC charge power recommendation sensor
- [ ] Output: Discharge allowed binary sensor
- [ ] Output: Current mode sensor (Grid Charge / Avoid Discharge / Allow Discharge)
- [ ] Output: 48h optimization schedule (with forecast attributes or calendar entity)
- [ ] Output: PV forecast sensor with forecast attributes
- [ ] Output: Price forecast sensor with forecast attributes
- [ ] Output: Consumption forecast sensor with forecast attributes
- [ ] Service: eos_ha.set_override (mode + duration)
- [ ] HACS-compatible repository structure (manifest.json, hacs.json)

### Out of Scope

- Direct inverter control (Fronius API) — user builds automations instead
- EVCC integration — deferred to v2
- Custom dashboard panel — HA native dashboard cards suffice
- EVopt optimization backend — EOS Server only for v1
- OpenHAB integration — HA only
- Multiple price API sources — prices come from existing HA entity
- Open-Meteo / Forecast.Solar / Solcast PV sources — Akkudoktor only for v1
- Web server / Flask dashboard — replaced by HA native UI
- MQTT discovery — no longer needed, entities are native HA

## Context

**Existing codebase:** eos-ha is a mature Python application (v0.2.30) that runs as a Docker container. It has a well-structured interface pattern with pluggable adapters for data sources, optimization backends, and device control. The optimization logic, EOS request format handling, and Akkudoktor API integration can be adapted for the HA integration.

**Architecture shift:** The current system is a standalone orchestrator with its own web server, MQTT publisher, and direct hardware control. The HA integration strips this down to: data collection (from HA entities + Akkudoktor API) → EOS optimization → entity exposure. No web server, no MQTT, no direct hardware control.

**Key reusable code:**
- `src/interfaces/optimization_backends/optimization_backend_eos.py` — EOS Server communication
- `src/interfaces/pv_interface.py` — Akkudoktor PV forecast fetching
- `src/interfaces/optimization_interface.py` — Request building logic
- `src/interfaces/base_control.py` — Control state interpretation logic
- `src/eos_ha.py` — Request creation and response parsing (extract, don't copy wholesale)

**HA Integration patterns:** Config Flow for initial setup (EOS server URL, location for PV), Options Flow for entity selection and parameter tuning. Entity platform pattern for sensors, binary sensors, number entities. DataUpdateCoordinator for periodic optimization cycle.

## Constraints

- **Platform**: Home Assistant custom integration (Python, async)
- **Distribution**: HACS-compatible (manifest.json, hacs.json, proper directory structure)
- **Async**: Must use async/await throughout (HA requirement) — current code uses sync requests + threading
- **Dependencies**: Minimize external dependencies; prefer HA built-in libraries (aiohttp over requests)
- **Config**: Config Flow + Options Flow (no YAML configuration)
- **Entities**: Follow HA entity naming conventions and best practices

## Key Decisions

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| No direct inverter control | User wants flexibility to build own automations | — Pending |
| Prices from HA entity, not API | Tibber HA integration already provides prices; avoid duplicate API calls | — Pending |
| Akkudoktor API for PV forecast | User preference; simplest single source for v1 | — Pending |
| EOS Server only (no EVopt) | Simplify v1 scope | — Pending |
| Number entities for battery params | Allows automation-driven parameter changes | — Pending |
| Config Flow + Options Flow | Standard HA pattern for user-friendly configuration | — Pending |
| HACS distribution | Makes installation easy for other users | — Pending |

---
*Last updated: 2026-02-14 after initialization*
