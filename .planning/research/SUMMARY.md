# Project Research Summary

**Project:** EOS Connect Home Assistant Integration
**Domain:** Home Assistant Custom Integration (Energy Optimization)
**Researched:** 2026-02-14
**Confidence:** HIGH

## Executive Summary

EOS Connect is a Home Assistant custom integration that bridges the existing EOS optimization server (currently a Docker-based standalone service) with Home Assistant's ecosystem. The research reveals this is a classic migration from synchronous, threaded Flask/MQTT architecture to Home Assistant's async, event-driven model. Experts in this domain universally recommend the DataUpdateCoordinator pattern for polling external optimization APIs, ConfigFlow for modern UI-based setup, and strict adherence to async patterns to avoid blocking Home Assistant's event loop.

The recommended approach leverages Home Assistant's built-in patterns rather than reimplementing optimization logic. The integration should read inputs from existing HA entities (electricity prices from Tibber/Nordpool, battery SOC from inverter integrations), call the EOS server for optimization decisions, and expose results as sensor/number entities that users consume in automations. This separation keeps the integration lightweight and maintainable while leveraging the mature EOS optimization backend.

Key risks center on async migration pitfalls—specifically blocking operations, incorrect DataUpdateCoordinator usage, and timezone handling for energy data. The migration from requests/Flask/threading to aiohttp/asyncio requires careful auditing of all I/O operations. Energy Dashboard integration demands precise state_class and device_class configuration. These risks are well-documented and preventable with established patterns from Home Assistant's developer documentation.

## Key Findings

### Recommended Stack

Home Assistant 2026.x requires Python 3.13+ and full async architecture. The stack centers on Home Assistant's native helpers rather than external frameworks.

**Core technologies:**
- **Python 3.13.2+**: Home Assistant 2026 runtime requirement (3.12 is deprecated)
- **DataUpdateCoordinator**: Centralized polling prevents duplicate API calls; handles error recovery automatically
- **aiohttp (via async_get_clientsession)**: Async HTTP for EOS server and Akkudoktor API calls; use HA's session for connection pooling
- **ConfigFlow + OptionsFlow**: Modern UI-based configuration (YAML config is deprecated; HACS requires this)
- **CoordinatorEntity base class**: Auto-handles should_poll=False, coordinator subscriptions, and availability management
- **pytest-homeassistant-custom-component**: Test framework matching HA 2026 (version 0.13.313+)
- **Ruff 0.15.1+**: Linting and formatting (replaces Black/flake8; matches HA quality standards)

**Critical migration requirements:**
- Remove: Flask, gevent, requests, threading, paho-mqtt (all synchronous/blocking)
- Replace: requests → aiohttp, threading.Timer → DataUpdateCoordinator, time.sleep() → asyncio.sleep()
- Keep: open-meteo-solar-forecast (for Akkudoktor API integration)

**Version compatibility notes:**
- Home Assistant 2026.1+ ships with aiohttp 3.13.3
- Use asyncio.timeout() (stdlib) not async_timeout package (deprecated)
- HACS requires manifest.json with version field (SemVer or CalVer format)

### Expected Features

Research shows energy optimization integrations have clear table stakes vs differentiators.

**Must have (table stakes):**
- **Config Flow setup** — users expect UI-based config with server URL, location, entity selectors (not YAML)
- **Options Flow** — runtime configuration changes without deleting integration
- **Price forecast sensor** — read from existing Tibber/Nordpool entities; expose with hourly attributes
- **PV forecast sensor** — fetch from Akkudoktor API (48h); expose hourly forecast as attributes
- **Current recommendation sensors** — AC/DC charge power (W), current mode (text); "what should I do NOW"
- **Discharge control binary sensor** — on/off state for automation triggers
- **Battery SOC integration** — read from user-selected HA entity; handle both % and Wh formats
- **Energy Dashboard compatible** — proper device_class (energy/power), state_class (total_increasing/measurement), units (kWh/W)
- **Periodic optimization** — DataUpdateCoordinator with configurable interval (default 5-15min)
- **Error handling / diagnostics** — integration quality scale requirement; expose EOS server status

**Should have (competitive advantage):**
- **48h schedule visualization** — expose optimization plan as calendar entity or enhanced attributes (users want to see full plan, not just current)
- **Battery parameter number entities** — capacity, max charge/discharge power, efficiency; allows automation-driven changes (vacation mode, seasonal profiles)
- **Manual override service** — eos_connect.set_override with mode (force charge/discharge/auto) + duration; users need temporary overrides
- **Cost savings sensor** — calculate saved € based on actual vs grid-only scenario; gamification/ROI visibility
- **Live vs forecast comparison** — shows how actual diverges from predicted; builds trust in optimization

**Defer (v2+):**
- **Multiple price/PV forecast sources** — users already have Tibber/Nordpool; Akkudoktor sufficient for v1
- **EVopt backend support** — alternative optimizer; adds testing complexity
- **Multi-inverter/multi-battery** — complex UI; rare use case
- **Direct inverter control** — creates tight hardware coupling; users prefer flexibility to build own automations

**Anti-features (avoid):**
- Don't build price APIs (use existing Tibber/Nordpool integrations)
- Don't create custom dashboard panel (HA cards are powerful enough)
- Don't support YAML config (deprecated; Config Flow required for HACS)
- Don't poll faster than 5 minutes (optimization is computationally expensive; battery control is slow-changing)

### Architecture Approach

The architecture follows Home Assistant's standard integration pattern with DataUpdateCoordinator as the orchestration hub.

**Major components:**

1. **Config Flow layer** — handles UI-based setup and runtime options
   - ConfigFlow: initial setup (server URL, location, validation)
   - OptionsFlow: runtime changes (entity selectors, battery params, intervals)
   - Validates API connectivity before completing setup

2. **Integration core (__init__.py)** — entry point and lifecycle management
   - Creates DataUpdateCoordinator instance
   - Forwards setup to entity platforms (sensor, binary_sensor, number)
   - Registers services (force_update, set_override)
   - Stores coordinator in hass.data[DOMAIN][entry_id]

3. **DataUpdateCoordinator** — centralized data fetching and distribution
   - Reads HA entity states (price, SOC, consumption via hass.states.get)
   - Calls Akkudoktor API for PV forecast (async)
   - Calls EOS optimization server (async)
   - Updates all entities simultaneously (prevents duplicate API calls)
   - Handles errors: raises UpdateFailed (temporary) or ConfigEntryAuthFailed (reauth)
   - Configurable update_interval (default 5-15min)

4. **Entity platforms** — CoordinatorEntity subclasses consuming coordinator data
   - sensor.py: optimization results (charge power, mode, forecasts)
   - binary_sensor.py: discharge allowed, optimization status
   - number.py: battery parameters (capacity, max charge/discharge, SOC limits)
   - All inherit from CoordinatorEntity (auto-handles should_poll=False, availability)

5. **External interfaces**
   - Read from HA state machine: hass.states.get() for input entities
   - Akkudoktor PV API: async HTTP via aiohttp
   - EOS optimization server: async HTTP via aiohttp
   - Service handlers: allow manual triggers and overrides

**Data flow pattern:**
Timer triggers → Coordinator._async_update_data → Read HA states + Call APIs → Store in coordinator.data → Notify entities → Entities update from coordinator.data → HA state machine updates → Frontend displays

**Build order (incremental testing):**
1. manifest.json + const.py + minimal __init__.py
2. Config flow (test: integration appears in Add Integration UI)
3. Coordinator with hardcoded data (test: polling works)
4. First sensor platform (test: entity appears and updates)
5. Additional platforms (binary_sensor, number)
6. Services + Options Flow
7. Error handling + polish

### Critical Pitfalls

Research identified 8 critical pitfalls with high impact if not addressed early:

1. **Blocking operations in async event loop** — using requests, time.sleep(), pandas/numpy, or file I/O directly freezes entire HA system
   - **Avoid:** Replace requests with aiohttp; wrap blocking operations in hass.async_add_executor_job(); use asyncio.sleep() not time.sleep()
   - **Impact:** HA UI becomes unresponsive; other integrations stall
   - **Phase:** Must fix in Phase 1 (Architecture Foundation)

2. **DataUpdateCoordinator misuse** — not calling async_config_entry_first_refresh before entity setup causes entities to never update or become unavailable permanently
   - **Avoid:** Call await coordinator.async_config_entry_first_refresh() in async_setup_entry BEFORE forwarding to platforms; raise UpdateFailed for temporary errors, ConfigEntryAuthFailed for auth failures
   - **Impact:** Entities stuck unavailable after restart; double polling if should_poll=True
   - **Phase:** Phase 2 (Data Coordination Layer)

3. **Unique ID instability or absence** — entities without unique_id can't be customized; changing unique_id creates duplicates
   - **Avoid:** Set stable unique_id in entity.__init__ using format {domain}_{device_id}_{entity_type}; never use IP/hostname/UUIDs
   - **Impact:** Users can't rename entities; customizations don't persist; duplicates on restart
   - **Phase:** Phase 3 (Entity Structure) — must be correct from first entity

4. **Energy sensor state_class mistakes** — wrong state_class prevents Energy Dashboard integration
   - **Avoid:** Cumulative energy: device_class=energy, state_class=total_increasing, NO last_reset; Instantaneous power: device_class=power, state_class=measurement
   - **Impact:** Sensors missing from Energy Dashboard; validation errors; wrong statistics
   - **Phase:** Phase 3 (Entity Structure) — critical for energy integration

5. **Timezone misalignment** — mixing naive and aware datetimes causes data offset by hours; daily totals reset at wrong time
   - **Avoid:** Use dt_util.now() not datetime.now(); use full timezone names (Europe/Berlin not CET); align forecast data on UTC boundaries
   - **Impact:** Energy Dashboard shows yesterday's data as today; DST transition errors
   - **Phase:** Phase 2 (Data Coordination Layer) — affects all time-series handling

6. **Config Flow validation gaps** — accepting invalid config causes setup failures; users can create duplicate entries
   - **Avoid:** Set unique_id after discovery; call _abort_if_unique_id_configured(); validate API connectivity in config flow; implement async_step_reauth for auth failures
   - **Impact:** Multiple entries for same device; setup fails silently; cryptic error messages
   - **Phase:** Phase 4 (Config Flow) — before HACS publication

7. **Entity state properties doing I/O** — network calls in property getters cause massive performance degradation
   - **Avoid:** Properties MUST only return data from memory (self._cached_value or self.coordinator.data); fetch data in coordinator update, not property getters
   - **Impact:** UI freezes; excessive network requests; timeouts
   - **Phase:** Phase 3 (Entity Structure) — core entity pattern

8. **Threading replacement misconceptions** — using asyncio.create_task() instead of hass.async_create_task() causes task leaks
   - **Avoid:** Use DataUpdateCoordinator for periodic updates; use hass.async_create_task() not asyncio.create_task(); implement async_unload_entry to cancel tasks
   - **Impact:** Memory leaks; tasks continue after reload; shutdown hangs
   - **Phase:** Phase 1 (Architecture Foundation) — establish correct task patterns

## Implications for Roadmap

Based on dependencies discovered in research, suggested phase structure emphasizes foundation-first to avoid costly refactoring:

### Phase 1: Async Foundation & Minimal Config Flow
**Rationale:** Must establish async patterns before building on them; blocking operations in early phases require full rewrites. Config Flow enables incremental testing.

**Delivers:**
- manifest.json, const.py, minimal __init__.py (async_setup, async_setup_entry stubs)
- ConfigFlow with server URL validation (async aiohttp call)
- Passes HA integration load test

**Addresses:**
- Table stakes: Config Flow setup (required for HACS)
- Stack: Python 3.13+, aiohttp validation pattern
- Pitfalls: Blocking operations (#1), threading patterns (#8)

**Avoids:** Using requests/threading/Flask patterns that require later migration

**Research flag:** Standard pattern; skip research-phase (well-documented in HA docs)

---

### Phase 2: DataUpdateCoordinator & Input Reading
**Rationale:** Coordinator is the heart of the integration; all entities depend on it. Must be stable before building entities. Tests coordinator pattern with external API calls.

**Delivers:**
- coordinator.py with _async_update_data implementation
- Reads HA entity states (price, SOC) via hass.states.get()
- Calls Akkudoktor API for PV forecast (async)
- Calls EOS server for optimization (async)
- Error handling: UpdateFailed, ConfigEntryAuthFailed
- Timezone-aware datetime handling with dt_util

**Addresses:**
- Stack: DataUpdateCoordinator pattern, aiohttp for external APIs
- Pitfalls: Coordinator misuse (#2), timezone alignment (#5)
- Architecture: Central data fetching component

**Uses:**
- aiohttp via async_get_clientsession(hass)
- asyncio.timeout() for request timeouts
- dt_util.now() for timezone-aware timestamps

**Avoids:** Polling in entity properties; naive datetime usage

**Research flag:** Standard pattern; may need light research-phase for EOS server API schema

---

### Phase 3: Core Entity Platforms (Sensor, Binary Sensor)
**Rationale:** After coordinator is stable, build entities that consume its data. Sensor platform is most critical (exposes optimization results). Must get unique_id, state_class, device_class correct from start.

**Delivers:**
- sensor.py: AC/DC charge power, mode, PV forecast, price forecast
- binary_sensor.py: discharge_allowed, optimization_status
- CoordinatorEntity base class usage
- Proper unique_id format: {domain}_{entry_id}_{entity_type}
- Energy Dashboard compatibility: device_class, state_class, units
- extra_state_attributes for forecast data (hourly arrays)

**Addresses:**
- Table stakes: Current recommendation sensors, discharge binary sensor, Energy Dashboard compatible
- Pitfalls: Unique ID stability (#3), energy sensor state_class (#4), properties doing I/O (#7)
- Features: Price forecast sensor, PV forecast sensor, current recommendations

**Implements:**
- CoordinatorEntity pattern (auto-handles should_poll=False)
- Sensor with device_class=power, state_class=measurement (instantaneous power)
- Sensor with device_class=energy, state_class=total_increasing (cumulative energy if needed)
- Binary sensor for discharge control (automation trigger)

**Avoids:** Missing unique_id; wrong state_class; I/O in property getters

**Research flag:** Standard pattern; skip research-phase (sensor entities well-documented)

---

### Phase 4: Options Flow & Number Entities
**Rationale:** After core entities work, add runtime configurability. Number entities enable dynamic battery parameter changes without Options Flow UI.

**Delivers:**
- OptionsFlow for runtime configuration (entity selectors, update interval, battery params)
- number.py: battery_capacity, max_charge_power, max_discharge_power, min_soc, max_soc
- Update listener to reload coordinator when options change
- Entity selectors in Options Flow (filtered by device_class)

**Addresses:**
- Table stakes: Options Flow
- Differentiators: Battery parameter number entities (automation-driven config changes)
- Features: Runtime configuration without integration removal

**Implements:**
- NumberEntity with async_set_native_value()
- native_min_value, native_max_value, native_step
- Options Flow with vol.Schema validation
- update_listener callback pattern

**Avoids:** Hardcoding battery params in config; forcing users to delete/re-add for config changes

**Research flag:** Standard pattern; skip research-phase (Options Flow well-documented)

---

### Phase 5: Services & Manual Control
**Rationale:** After automatic optimization works, add manual override capabilities. Services registered at integration level (async_setup) for availability.

**Delivers:**
- services.yaml: force_update, set_override
- Service handlers in __init__.py
- Override state machine (manual vs automatic mode)
- Override timeout mechanism (resume automatic after duration)

**Addresses:**
- Differentiators: Manual override service (force charge/discharge for edge cases)
- Features: Users need temporary control during storms, guests, etc.

**Implements:**
- hass.services.async_register() in async_setup (not async_setup_entry)
- vol.Schema for service validation
- Coordinator method: async_request_refresh() for force_update

**Avoids:** Registering services in async_setup_entry (services disappear on reload)

**Research flag:** Standard pattern; skip research-phase

---

### Phase 6: Diagnostics & Error Handling Polish
**Rationale:** Integration Quality Scale requirement; essential for user support and debugging.

**Delivers:**
- diagnostics.py platform
- Downloadable diagnostics file with sanitized config + last EOS response
- Status sensor: last_update, next_update, optimization_status
- Graceful degradation when input entities unavailable
- User-friendly error messages in strings.json

**Addresses:**
- Table stakes: Error handling / diagnostics
- Features: Optimization quality metrics, status visibility

**Implements:**
- async_get_config_entry_diagnostics()
- Sensor for last optimization timestamp
- Binary sensor for connectivity status
- Error mapping in strings.json (common errors → user-friendly messages)

**Avoids:** Exposing sensitive data in diagnostics; cryptic error messages

**Research flag:** Standard pattern; skip research-phase

---

### Phase 7: Enhanced Features (Schedule Viz, Cost Savings)
**Rationale:** After MVP is stable, add differentiators based on user feedback.

**Delivers:**
- 48h schedule as calendar entity OR enhanced attributes (service returning forecast data)
- Cost savings sensor (daily/monthly € saved)
- Live vs forecast comparison sensors
- Consumption forecast sensor

**Addresses:**
- Differentiators: 48h schedule visualization, cost savings sensor, forecast comparison
- Features: Users want to see full plan; ROI visibility

**Implements:**
- Calendar entity for schedule (better UX than JSON attributes)
- Sensor for cost savings calculation
- Attributes with actual vs forecast data

**Defers to user feedback:** Add only if requested during v1 usage

**Research flag:** May need research-phase for calendar entity pattern (less common in energy integrations)

---

### Phase 8: HACS Packaging & Documentation
**Rationale:** Final polish for community distribution.

**Delivers:**
- hacs.json
- README with installation instructions
- Example automations (discharge control, override scenarios)
- GitHub release workflow
- Pre-commit hooks (Ruff, mypy, codespell, yamllint)

**Addresses:**
- Table stakes: HACS compatibility
- Features: Distribution expectation

**Implements:**
- manifest.json with all required HACS fields
- GitHub releases for version tracking
- Example dashboard YAML (ApexCharts for schedule visualization)

**Avoids:** Incomplete manifest; missing documentation

**Research flag:** Skip research-phase (HACS requirements well-documented)

---

### Phase Ordering Rationale

1. **Foundation first (Phases 1-2):** Async patterns and coordinator are architectural; fixing blocking operations later requires rewrites
2. **Entities after coordinator (Phase 3):** Entities depend on stable coordinator; test coordinator alone before building entities
3. **Configuration after core (Phase 4):** Options Flow needs working entities to be useful
4. **Services after automatic mode (Phase 5):** Manual override only makes sense after automatic optimization works
5. **Diagnostics before launch (Phase 6):** Essential for debugging user issues
6. **Enhancements after validation (Phase 7):** Add based on user feedback, not speculation
7. **Packaging last (Phase 8):** Polish after functionality is complete

**Dependency chain:**
- Phase 1 → Phase 2 (coordinator needs async foundation)
- Phase 2 → Phase 3 (entities need coordinator)
- Phase 3 → Phase 4 (number entities extend sensor pattern)
- Phase 3 → Phase 5 (services need working coordinator)
- Phase 3 → Phase 6 (diagnostics need entities)
- Phase 6 → Phase 7 (enhancements need stable base)
- Phase 7 → Phase 8 (packaging needs complete functionality)

### Research Flags

**Phases needing deeper research during planning:**
- **Phase 2:** Light research for EOS server API schema (request/response format, error codes)
- **Phase 7:** Research calendar entity pattern if 48h schedule visualization prioritized (less common in energy domain)

**Phases with standard patterns (skip research-phase):**
- **Phase 1:** Config Flow setup (well-documented, numerous examples)
- **Phase 3:** Sensor/binary sensor entities with coordinator (standard HA pattern)
- **Phase 4:** Options Flow + number entities (well-documented)
- **Phase 5:** Service registration (standard pattern)
- **Phase 6:** Diagnostics platform (integration quality scale requirement, documented)
- **Phase 8:** HACS packaging (clear requirements, checklist available)

## Confidence Assessment

| Area | Confidence | Notes |
|------|------------|-------|
| Stack | HIGH | Official HA developer docs verified; Python version requirements confirmed from HA 2026 release notes; aiohttp/coordinator patterns are standard |
| Features | HIGH | Compared 5+ energy optimization integrations (EMHASS, Predbat, Tibber, Nordpool, Powerwall); table stakes clearly established; competitive analysis robust |
| Architecture | HIGH | DataUpdateCoordinator pattern is the standard HA approach; component boundaries match official integration structure; build order tested across multiple integration blueprints |
| Pitfalls | MEDIUM-HIGH | Critical pitfalls verified from official docs + community issue tracking; migration-specific risks identified from codebase analysis (requests/Flask/threading removal); timezone handling confirmed from Energy Dashboard docs |

**Overall confidence:** HIGH

Research draws primarily from official Home Assistant developer documentation (architecture, coordinator, config flow, entity platforms), HACS requirements (verified against publication checklist), and analysis of 5 comparable integrations. Pitfall research combines official async guidelines with community issue reports (GitHub, HA forums) and codebase analysis of migration requirements.

### Gaps to Address

**During Phase 2 planning:**
- EOS server API schema details (request format, response structure, error codes) — need to inspect existing codebase or API documentation
- Optimal coordinator update interval (default 5min vs 15min) — depends on EOS server computational cost and battery response time
- Akkudoktor API rate limits (if any) — validate no restrictions on polling frequency

**During Phase 3 planning:**
- Exact attribute structure for forecast data (hourly arrays) — validate against ApexCharts card requirements for visualization
- Energy sensor units (kWh vs Wh) — confirm EOS server output format and convert if needed

**During Phase 7 (if implemented):**
- Calendar entity implementation details — less common pattern in energy integrations; may need research-phase

**Validation approach:**
- Phase 1: Test with existing EOS server API endpoint to validate connectivity pattern
- Phase 2: Inspect coordinator.data structure with logging to verify all required fields present
- Phase 3: Test sensors appear in Energy Dashboard selector (confirms device_class/state_class correct)
- Phase 4: Test Options Flow changes trigger coordinator update
- Phase 5: Test services appear in Developer Tools → Services
- Phase 6: Download diagnostics file to verify sanitization and completeness

## Sources

### Primary (HIGH confidence)
- [Integration architecture | Home Assistant Developer Docs](https://developers.home-assistant.io/docs/architecture_components/)
- [Fetching data | Home Assistant Developer Docs](https://developers.home-assistant.io/docs/integration_fetching_data/)
- [Config entries | Home Assistant Developer Docs](https://developers.home-assistant.io/docs/config_entries_index/)
- [Config flow | Home Assistant Developer Docs](https://developers.home-assistant.io/docs/config_entries_config_flow_handler/)
- [Options flow | Home Assistant Developer Docs](https://developers.home-assistant.io/docs/config_entries_options_flow_handler/)
- [Sensor entity | Home Assistant Developer Docs](https://developers.home-assistant.io/docs/core/entity/sensor/)
- [Binary sensor entity | Home Assistant Developer Docs](https://developers.home-assistant.io/docs/core/entity/binary-sensor/)
- [Number entity | Home Assistant Developer Docs](https://developers.home-assistant.io/docs/core/entity/number/)
- [Integration service actions | Home Assistant Developer Docs](https://developers.home-assistant.io/docs/dev_101_services/)
- [Working with Async | Home Assistant Developer Docs](https://developers.home-assistant.io/docs/asyncio_working_with_async/)
- [Blocking operations | Home Assistant Developer Docs](https://developers.home-assistant.io/docs/asyncio_blocking_operations/)
- [Integration Quality Scale | Home Assistant Developer Docs](https://developers.home-assistant.io/docs/core/integration-quality-scale/)
- [HACS Integration Requirements | HACS](https://www.hacs.xyz/docs/publish/integration/)
- [Integration manifest | Home Assistant Developer Docs](https://developers.home-assistant.io/docs/creating_integration_manifest/)
- [Home Assistant Energy Dashboard | Home Assistant](https://www.home-assistant.io/docs/energy/)
- [Home Assistant 2026 Release Notes](https://pypi.org/project/homeassistant/) — Python 3.13+ requirement

### Secondary (MEDIUM confidence)
- [Building a Home Assistant Custom Component Series | Automate The Things](https://aarongodfrey.dev/home%20automation/building_a_home_assistant_custom_component_part_1/)
- [Use CoordinatorEntity with DataUpdateCoordinator | Automate The Things](https://aarongodfrey.dev/home%20automation/use-coordinatorentity-with-the-dataupdatecoordinator/)
- [Home Assistant: Concurrency Model | The Candid Startup](https://www.thecandidstartup.org/2025/10/20/home-assistant-concurrency-model.html)
- [EMHASS Integration Analysis](https://github.com/davidusb-geek/emhass) — competitor feature comparison
- [Predbat Integration Analysis](https://github.com/springfall2008/batpred) — competitor feature comparison
- [Tibber Integration](https://www.home-assistant.io/integrations/tibber/) — price sensor patterns
- [Nord Pool Integration](https://www.home-assistant.io/integrations/nordpool/) — price sensor patterns
- [Forecast.Solar Integration](https://www.home-assistant.io/integrations/forecast_solar/) — PV forecast patterns
- [Tesla Powerwall Integration](https://www.home-assistant.io/integrations/powerwall/) — battery optimization patterns

### Tertiary (LOW-MEDIUM confidence)
- [HA Community: EMHASS Thread](https://community.home-assistant.io/t/emhass-an-energy-management-for-home-assistant/338126) — user feature requests
- [HA Community: Battery Automation Patterns](https://community.home-assistant.io/t/automation-of-battery-discharge/878641) — user automation patterns
- [HA Community: DataUpdateCoordinator Issues](https://community.home-assistant.io/t/dataupdatecoordinator-based-integrations-become-unavailable-after-a-few-hours/986502) — pitfall validation
- [HA Community: Energy Dashboard Timezones](https://community.home-assistant.io/t/energy-dashboard-and-timezones/348218) — timezone pitfall validation
- [GitHub Issue: Energy state_class validation](https://github.com/home-assistant/core/issues/87376) — state_class pitfall
- EOS Connect codebase analysis — migration requirements (requests/Flask/threading → aiohttp/asyncio)

---
*Research completed: 2026-02-14*
*Ready for roadmap: yes*
