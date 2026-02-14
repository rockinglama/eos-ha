---
phase: 01-foundation-data-flow
plan: 01
subsystem: config_flow
tags: [integration-skeleton, config-flow, hacs, entity-selection, eos-validation]
requires: []
provides: [config-entry, integration-metadata, config-flow-ui]
affects: [custom_components/eos_connect]
tech_stack:
  added:
    - Home Assistant Config Flow pattern
    - aiohttp for async HTTP (EOS health check)
    - voluptuous for schema validation
    - HA entity selectors for UI
  patterns:
    - 3-step wizard flow (server → entities → battery)
    - Async server validation with timeout
    - Home location auto-retrieval from HA config
    - Unique ID constraint (single instance only)
key_files:
  created:
    - custom_components/eos_connect/__init__.py
    - custom_components/eos_connect/manifest.json
    - custom_components/eos_connect/hacs.json
    - custom_components/eos_connect/const.py
    - custom_components/eos_connect/config_flow.py
    - custom_components/eos_connect/strings.json
    - custom_components/eos_connect/translations/en.json
  modified: []
decisions:
  - title: Battery capacity in kWh (not Wh)
    rationale: User-friendly units match common battery spec sheets; 10 kWh default suits mid-range home batteries
    impact: All battery capacity inputs/outputs use kWh throughout integration
  - title: Location from HA config, not user input
    rationale: HA already has home location configured; avoid duplicate data entry and potential inconsistency
    impact: Config Flow pulls latitude/longitude from self.hass.config; aborts if missing
  - title: Single integration instance via unique_id
    rationale: EOS Connect manages one optimization setup per HA instance; multiple instances would conflict
    impact: async_set_unique_id(DOMAIN) prevents duplicate config entries
metrics:
  duration_minutes: 2
  tasks_completed: 2
  files_created: 7
  files_modified: 0
  commits: 2
  completed_date: "2026-02-14"
---

# Phase 01 Plan 01: HACS Integration Skeleton & Config Flow Summary

**One-liner:** HACS-compatible integration skeleton with 3-step Config Flow for EOS server validation, entity selection, and battery parameter configuration.

## What Was Built

Created the foundational directory structure and Config Flow for the EOS Connect Home Assistant custom integration. Users can now install via HACS and configure the integration through HA's UI with a 3-step wizard that validates the EOS server connection, selects energy data entities, and sets battery parameters.

### Task 1: HACS Integration Skeleton and Constants
**Commit:** 4c14d63

Created the `custom_components/eos_connect/` directory with HACS-compatible metadata and shared constants:

- **manifest.json**: Integration manifest with `config_flow: true`, `domain: eos_connect`, and `iot_class: local_polling`. No external requirements (aiohttp is built into HA).
- **hacs.json**: HACS metadata enabling installation via HACS.
- **const.py**: All shared constants including:
  - `DOMAIN = "eos_connect"`
  - Config key constants: `CONF_EOS_URL`, `CONF_PRICE_ENTITY`, `CONF_SOC_ENTITY`, `CONF_CONSUMPTION_ENTITY`, `CONF_BATTERY_CAPACITY`, `CONF_MAX_CHARGE_POWER`, `CONF_MIN_SOC`, `CONF_MAX_SOC`, `CONF_INVERTER_POWER`
  - Sensible defaults: 10.0 kWh battery, 5000W max charge, 10-90% SOC range, 10000W inverter
  - Akkudoktor API URL and cache settings
- **__init__.py**: Stub setup/unload functions (will be completed in Plan 02)

### Task 2: 3-Step Config Flow with EOS Validation
**Commit:** 3f13366

Implemented `EOSConnectConfigFlow` with three progressive steps:

**Step 1 - EOS Server URL (`async_step_user`):**
- Collects EOS server URL
- Validates server by calling `/v1/health` endpoint (checks `status: "alive"`)
- Stores EOS version from response
- Auto-retrieves latitude/longitude from `self.hass.config` (not user input)
- Aborts with `no_home_location` if HA home zone not configured
- Error handling: `cannot_connect` (network), `timeout` (10s), `invalid_response` (status != alive)
- Sets unique_id to prevent duplicate entries

**Step 2 - Entity Selection (`async_step_entities`):**
- Price entity selector (all sensors, no device_class filter for Tibber compatibility)
- SOC entity selector (highlights battery device_class sensors)
- Consumption entity selector (all sensors)
- Uses HA's native entity selectors for type-safe UI

**Step 3 - Battery Parameters (`async_step_battery`):**
- Battery capacity (kWh): 0.5-200.0 range, default 10.0
- Max charge power (W): 100-50000 range, default 5000
- Min SOC (%): 0-100 range, default 10
- Max SOC (%): 0-100 range, default 90
- Inverter power (W): 100-100000 range, default 10000
- All fields pre-filled with sensible defaults
- Creates config entry with all accumulated data

**UI Strings:**
- `strings.json` and `translations/en.json` with identical structure
- All step titles, descriptions, field labels, error messages, and abort reasons

## Deviations from Plan

None - plan executed exactly as written.

## Verification Results

All success criteria met:

- ✓ All 7 files exist with valid content
- ✓ Config Flow class inherits from ConfigFlow with domain=DOMAIN
- ✓ 3 steps implemented: user → entities → battery
- ✓ EOS validation checks `/v1/health` for status "alive"
- ✓ Entity selectors use EntitySelector with appropriate device_class hints
- ✓ Battery capacity defaults to 10.0 kWh (not Wh)
- ✓ Location comes from HA config, not user input
- ✓ strings.json and translations/en.json are consistent
- ✓ All Python files pass `ast.parse()` (valid syntax)
- ✓ All JSON files are valid JSON

## Integration Points

**Provides to next plans:**
- Config entry data structure (EOS URL, lat/lon, entity IDs, battery params)
- DOMAIN constant for coordinator and entity platforms
- Config key constants for accessing stored data

**Depends on:**
- User's EOS server running and accessible at `/v1/health`
- HA home zone configured (latitude/longitude set)
- Existing HA entities for price, SOC, and consumption data

## Next Steps

Plan 02 will implement the DataUpdateCoordinator to run the optimization cycle, collect data from selected entities and Akkudoktor API, send requests to EOS server, and parse responses.

## Self-Check

Verifying all claims in this summary:

```bash
# Check created files exist
[ -f "custom_components/eos_connect/__init__.py" ] && echo "FOUND: __init__.py" || echo "MISSING: __init__.py"
[ -f "custom_components/eos_connect/manifest.json" ] && echo "FOUND: manifest.json" || echo "MISSING: manifest.json"
[ -f "custom_components/eos_connect/hacs.json" ] && echo "FOUND: hacs.json" || echo "MISSING: hacs.json"
[ -f "custom_components/eos_connect/const.py" ] && echo "FOUND: const.py" || echo "MISSING: const.py"
[ -f "custom_components/eos_connect/config_flow.py" ] && echo "FOUND: config_flow.py" || echo "MISSING: config_flow.py"
[ -f "custom_components/eos_connect/strings.json" ] && echo "FOUND: strings.json" || echo "MISSING: strings.json"
[ -f "custom_components/eos_connect/translations/en.json" ] && echo "FOUND: translations/en.json" || echo "MISSING: translations/en.json"

# Check commits exist
git log --oneline --all | grep -q "4c14d63" && echo "FOUND: 4c14d63" || echo "MISSING: 4c14d63"
git log --oneline --all | grep -q "3f13366" && echo "FOUND: 3f13366" || echo "MISSING: 3f13366"
```

**Result:**
```
FOUND: __init__.py
FOUND: manifest.json
FOUND: hacs.json
FOUND: const.py
FOUND: config_flow.py
FOUND: strings.json
FOUND: translations/en.json
FOUND: 4c14d63
FOUND: 3f13366
```

## Self-Check: PASSED
