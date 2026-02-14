# Domain Pitfalls: Home Assistant Custom Integration Development

**Domain:** Home Assistant Custom Integration (Energy Optimization)
**Researched:** 2026-02-14
**Confidence:** MEDIUM-HIGH

## Critical Pitfalls

Mistakes that cause rewrites or major issues.

---

### Pitfall 1: Blocking Operations in Async Event Loop

**What goes wrong:**
Synchronous I/O operations (file access, `requests` library, `time.sleep()`, pandas/numpy operations) executed directly in the event loop freeze Home Assistant entirely. Nothing else can run until the blocking operation completes, causing system-wide unresponsiveness.

**Why it happens:**
Developers migrating from synchronous Python apps assume they can wrap sync code with `async def` and it becomes non-blocking. The `requests` library, Flask endpoints, threading patterns, and data processing libraries (pandas/numpy) from standalone apps don't work in Home Assistant's async architecture.

**How to avoid:**
- Replace `requests` with `aiohttp` for all HTTP calls
- Wrap blocking operations in executor jobs: `await hass.async_add_executor_job(blocking_func, arg)`
- Replace `time.sleep(seconds)` with `await asyncio.sleep(seconds)`
- Move pandas/numpy data processing to executor jobs
- Never use `open()`, `Path.read_text()`, or file I/O directly—wrap in executor
- Starting in HA 2024.7.0, blocking operation detection will catch violations and log errors

**Warning signs:**
- Home Assistant UI becomes unresponsive during integration operations
- Logs show "Blocking call to X done in the event loop" warnings (HA 2024.7.0+)
- Coordinator updates cause temporary system freezes
- Other integrations become sluggish when your integration runs

**Phase to address:**
Phase 1: Architecture Foundation (Core async patterns must be established first)

**Sources:**
- [Blocking operations with asyncio | Home Assistant Developer Docs](https://developers.home-assistant.io/docs/asyncio_blocking_operations/)
- [Home Assistant: Concurrency Model](https://www.thecandidstartup.org/2025/10/20/home-assistant-concurrency-model.html)

---

### Pitfall 2: Threading Replacement Misconceptions

**What goes wrong:**
Converting periodic threading patterns (e.g., `threading.Timer`, background threads polling APIs) to async without understanding Home Assistant's task coordination leads to memory leaks, orphaned tasks, or tasks that don't cancel properly during shutdown/reload.

**Why it happens:**
Standalone apps use threads for periodic work. Home Assistant is single-threaded asyncio. Developers try `asyncio.create_task()` directly instead of `hass.async_create_task()`, missing Home Assistant's task tracking and cleanup mechanisms.

**How to avoid:**
- Use `hass.async_create_task()` not `asyncio.create_task()` for task creation
- For periodic updates, use `DataUpdateCoordinator` instead of manual task loops
- Never spawn background threads—use executor jobs for sync work
- Implement proper cleanup in `async_unload_entry()` to cancel tasks
- Use `track_time_interval` or `async_track_time_interval` for scheduled actions

**Warning signs:**
- Tasks continue running after integration reload/unload
- Memory usage grows over time (task leaks)
- Shutdown hangs or takes excessive time
- "Task was destroyed but it is pending!" errors in logs

**Phase to address:**
Phase 1: Architecture Foundation (Must establish correct task patterns early)

**Sources:**
- [Working with Async | Home Assistant Developer Docs](https://developers.home-assistant.io/docs/asyncio_working_with_async/)
- [Creating persistent async tasks - Development - Home Assistant Community](https://community.home-assistant.io/t/creating-persistent-async-tasks/180257)

---

### Pitfall 3: DataUpdateCoordinator Misuse

**What goes wrong:**
Incorrect DataUpdateCoordinator implementation causes entities to never update, become unavailable indefinitely after temporary API failures, or trigger excessive network requests.

**Why it happens:**
Developers don't understand coordinator's error handling model: raising `UpdateFailed` vs `ConfigEntryAuthFailed`, or they set `should_poll=True` on entities alongside coordinator (causing double polling), or they fail to call `async_config_entry_first_refresh()` before entity setup.

**How to avoid:**
- Always call `await coordinator.async_config_entry_first_refresh()` in `async_setup_entry()` BEFORE creating entities
- Raise `UpdateFailed` for temporary errors (API timeouts, network issues)
- Raise `ConfigEntryAuthFailed` for authentication failures (triggers reauth flow)
- Set `always_update=False` if data supports `__eq__` comparison (avoids unnecessary state writes)
- Use `CoordinatorEntity` base class—it sets `should_poll=False` automatically
- Never implement `async_update()` in entities when using coordinator
- Implement proper backoff with `retry_after` parameter when API provides rate limit signals

**Warning signs:**
- Entities show as "Unavailable" and never recover without HA restart
- Integration makes duplicate API calls (coordinator + entity polling)
- Entities don't update even though coordinator is polling
- State writes happen even when data hasn't changed (check DB growth)
- Logs show "Update interval X is not being respected"

**Phase to address:**
Phase 2: Data Coordination Layer (After async foundation is stable)

**Sources:**
- [Fetching data | Home Assistant Developer Docs](https://developers.home-assistant.io/docs/integration_fetching_data/)
- [DataUpdateCoordinator-based integrations become unavailable after a few hours](https://community.home-assistant.io/t/dataupdatecoordinator-based-integrations-become-unavailable-after-a-few-hours/986502)
- [Use CoordinatorEntity when using the DataUpdateCoordinator](https://aarongodfrey.dev/home%20automation/use-coordinatorentity-with-the-dataupdatecoordinator/)

---

### Pitfall 4: Unique ID Instability or Absence

**What goes wrong:**
Entities without `unique_id` cannot be customized in the UI (name, icon, entity_id changes). Entities with changing `unique_id` create duplicate entities on every restart. Entities with non-unique IDs across the integration cause registry corruption.

**Why it happens:**
Developers use user-configurable values (device names, IP addresses, URLs) as unique IDs, or they generate random UUIDs on entity creation, or they forget to set `unique_id` entirely. When migrating from MQTT-based discovery, the unique ID format may not match expectations.

**How to avoid:**
- Use stable, immutable identifiers: serial numbers, MAC addresses (via `format_mac()`), device-embedded IDs
- NEVER use IP addresses, hostnames, user-defined names, or generated UUIDs
- Set `unique_id` in entity's `__init__` and never change it
- Format: `{integration_domain}_{device_id}_{entity_type}` for consistency
- For config entry-based integrations with discovery, unique ID is MANDATORY
- Validate unique ID uniqueness within platform during entity creation

**Warning signs:**
- Users complain they can't rename entities in UI
- Duplicate entities appear after restart
- Entity customizations (icon, area) don't persist
- Error: "Platform X does not generate unique IDs"
- Users report lost automations after integration update

**Phase to address:**
Phase 3: Entity Structure (Must be correct from first entity implementation)

**Sources:**
- [This entity does not have a unique ID - Home Assistant FAQ](https://www.home-assistant.io/faq/unique_id/)
- [Entity | Home Assistant Developer Docs](https://developers.home-assistant.io/docs/core/entity/)
- [Config flow | Home Assistant Developer Docs](https://developers.home-assistant.io/docs/config_entries_config_flow_handler/)

---

### Pitfall 5: Config Flow Validation Gaps

**What goes wrong:**
Config flow accepts invalid configurations that cause setup failures later. Users can create duplicate entries for same device. Config flow doesn't gracefully handle authentication failures, expired tokens, or network timeouts. Error messages are cryptic or missing.

**Why it happens:**
Developers rely only on schema validation without additional checks. They don't call `self._abort_if_unique_id_configured()` after discovering devices. They don't catch API exceptions during validation and provide user-friendly errors. They don't implement `async_step_reauth()` for token renewal.

**How to avoid:**
- Set unique ID immediately after device discovery: `await self.async_set_unique_id(unique_id)`
- Call `self._abort_if_unique_id_configured()` to prevent duplicates
- Wrap API validation in try/except and populate `errors` dict with meaningful keys
- Implement `async_step_reauth` for authentication failures (required for Silver tier Quality Scale)
- Validate data beyond schema: check API reachability, credentials, device compatibility
- Use `title_placeholders` for dynamic error messages
- Never auto-create config entries from discovery—always confirm with user

**Warning signs:**
- Users create multiple entries for same device
- "Config flow could not be loaded: Invalid handler specified" errors
- Setup fails silently after config flow completes
- Users can't fix invalid credentials without deleting and re-adding integration
- Error messages say "Unknown error" or show Python exceptions

**Phase to address:**
Phase 4: Config Flow (After entities work, before HACS publication)

**Sources:**
- [Config flow | Home Assistant Developer Docs](https://developers.home-assistant.io/docs/config_entries_config_flow_handler/)
- [Error: Config flow could not be loaded - Home Assistant Community](https://community.home-assistant.io/t/error-config-flow-could-not-be-loaded-message-invalid-flow-specified/642802)

---

### Pitfall 6: Energy Sensor State Class Mistakes

**What goes wrong:**
Energy sensors don't appear in Energy Dashboard. Historical statistics are wrong or missing. Daily totals reset at wrong time. Sensors with `device_class: energy` but `state_class: measurement` trigger validation errors.

**Why it happens:**
Developers use wrong `state_class` for energy data. They don't understand difference between `total`, `total_increasing`, and `measurement`. They set `last_reset` when they shouldn't. They use `measurement` for cumulative energy instead of `total_increasing`.

**How to avoid:**
- For cumulative energy (kWh meter): `device_class: energy`, `state_class: total_increasing`, NO `last_reset`
- For instantaneous power (W): `device_class: power`, `state_class: measurement`
- For daily energy that resets: `device_class: energy`, `state_class: total`, set `last_reset` ONLY when reset happens
- Ensure values never decrease (except meter resets <10% trigger new cycle for `total_increasing`)
- Use proper `unit_of_measurement`: "kWh" for energy, "W" for power
- Never use `state_class: measurement` with `device_class: energy` (validation error in 2026)

**Warning signs:**
- Sensors missing from Energy Dashboard entity selector
- Error: "Entity is using state class 'measurement' which is impossible considering device class ('energy')"
- Statistics show flat lines or missing data
- Daily totals don't match expected consumption
- Database grows excessively (missing `state_class` stores every state change)

**Phase to address:**
Phase 3: Entity Structure (Critical for energy integration functionality)

**Sources:**
- [Sensor entity | Home Assistant Developer Docs](https://developers.home-assistant.io/docs/core/entity/sensor/)
- [Entity is using state class 'measurement' which is impossible considering device class ('energy')](https://github.com/home-assistant/core/issues/87376)
- [How to configure a Sensor for Energy Dashboard](https://community.home-assistant.io/t/how-to-configure-a-sensor-so-that-is-useable-in-in-the-energy-dashboard/478402)

---

### Pitfall 7: Timezone Misalignment in Energy Data

**What goes wrong:**
Energy Dashboard shows data offset by hours. Daily totals reset at 1am instead of midnight. Forecast data doesn't align with current time. Historical data jumps during DST transitions. Database queries return data for wrong day.

**Why it happens:**
Developers mix naive and timezone-aware datetimes. They use UTC for calculations but local time for display without conversion. They use `pytz` instead of `zoneinfo` (Python 3.9+). They use timezone abbreviations (CET, PST) instead of full names. They don't account for DST transitions in forecast data alignment.

**How to avoid:**
- Use full timezone names: "Europe/Berlin" not "CET" (handles DST automatically)
- Store all timestamps as UTC in HA (state machine handles this)
- Use `dt_util.now()` for current time (already timezone-aware)
- For forecast data: align on UTC hour boundaries, convert to local for display
- Never use `datetime.now()` without timezone—use `dt_util.now()`
- For energy calculations: ensure daily boundaries match user's local midnight
- Test with timezones that have 30-minute offsets (Adelaide, Newfoundland)
- Test before/after DST transitions

**Warning signs:**
- Energy Dashboard shows "yesterday's" data as "today"
- Reset times are 1 hour off
- Users in non-UTC timezones report incorrect timestamps
- Forecast data appears shifted by hours
- Errors during DST transition days

**Phase to address:**
Phase 2: Data Coordination Layer (Affects all time-series data handling)

**Sources:**
- [UTC & Time zone awareness - Home Assistant](https://www.home-assistant.io/blog/2015/05/09/utc-time-zone-awareness/)
- [Energy Dashboard and timezones - Home Assistant Community](https://community.home-assistant.io/t/energy-dashboard-and-timezones/348218)
- [Reset energy dashboard is not at midnight but 1 hour off](https://community.home-assistant.io/t/reset-energy-dashboard-is-not-at-midnight-but-1-hour-off-need-option-utc-1/514439)

---

### Pitfall 8: Entity State Properties Doing I/O

**What goes wrong:**
Entity properties (like `native_value`, `available`, `extra_state_attributes`) make network calls or disk I/O, causing massive performance degradation. State updates take seconds. UI freezes when opening entity pages.

**Why it happens:**
Developers treat properties as methods, fetching fresh data on every access. They don't understand that properties are called frequently (every state write, UI render) and must return from memory.

**How to avoid:**
- Properties MUST only return data from memory—NO I/O in property getters
- Fetch data in `async_update()` or coordinator's update method, store in instance variables
- Access stored data in properties: `return self._cached_value`
- For CoordinatorEntity: access `self.coordinator.data`
- Set `should_poll = False` when using coordinator or push updates
- Use `async_update()` for pull-based updates, coordinator for centralized polling

**Warning signs:**
- UI becomes slow or unresponsive when viewing entity
- High CPU usage from property access
- Excessive network requests (one per property access)
- Timeouts in property getters
- Error: "Detected I/O inside the event loop"

**Phase to address:**
Phase 3: Entity Structure (Core entity implementation pattern)

**Sources:**
- [Entity | Home Assistant Developer Docs](https://developers.home-assistant.io/docs/core/entity/)
- Official docs: "Properties should only return information from memory and not do I/O"

---

## Technical Debt Patterns

Shortcuts that seem reasonable but create long-term problems.

| Shortcut | Immediate Benefit | Long-term Cost | When Acceptable |
|----------|-------------------|----------------|-----------------|
| Using `async_add_executor_job` for all external calls instead of migrating to aiohttp | Faster initial migration | Performance degradation at scale; executor thread pool exhaustion | Only for CPU-bound operations (pandas/numpy); never for HTTP |
| Skipping unique_id implementation | Faster MVP | Users can't customize entities; breaks UI integration | Never acceptable for any integration |
| Hardcoding entity_id instead of using device/entity registry | Simpler initial code | Can't rename entities; breaks when users customize; multiple instances conflict | Never acceptable post-Config Flow |
| Single coordinator for all entity types | Simpler architecture | One slow API blocks all entities; can't tune update intervals per entity type | Acceptable if all data comes from single fast API |
| Using `time.time()` instead of `dt_util.now()` | Simpler code | Timezone bugs; DST issues; breaks energy calculations | Never acceptable for time-series/energy data |
| Polling individual entities instead of coordinator | Simpler initial pattern | Excessive API calls; rate limiting; battery drain on devices | Never acceptable for modern integrations (violates Quality Scale Bronze tier) |
| Skipping `async_unload_entry` implementation | Faster MVP | Memory leaks; tasks don't cancel; can't reload without HA restart | Never acceptable (required for integration reload) |

---

## Integration Gotchas

Common mistakes when connecting to external services.

| Integration | Common Mistake | Correct Approach |
|-------------|----------------|------------------|
| **MQTT (existing)** | Assuming migration from MQTT-based HA integration to native integration preserves entity_ids | Plan for entity renaming; provide migration docs; use same unique_id format as MQTT discovery to preserve entity registry |
| **aiohttp sessions** | Creating new session per request | Use `hass.helpers.aiohttp_client.async_get_clientsession()` for shared connection pooling |
| **Optimizer APIs (EOS/EVopt)** | Blocking requests library, no retry logic | Migrate to aiohttp; implement exponential backoff; handle JSON decode errors; validate response schema |
| **Home Assistant API (data collection)** | Querying sensor states synchronously | Use `hass.states.get()` for current state; `async_track_state_change_event` for updates |
| **Forecast APIs (solar, weather)** | Not caching; polling on every coordinator update | Cache forecast data; refresh only when stale (e.g., hourly); use ETag/If-Modified-Since headers |
| **Config entry updates** | Modifying config without reload trigger | Use `hass.config_entries.async_update_entry(entry, data=new_data)` then reload |
| **Service calls** | Blocking service calls from coordinator | Use `await hass.services.async_call()` for service invocation |

---

## Performance Traps

Patterns that work at small scale but fail as usage grows.

| Trap | Symptoms | Prevention | When It Breaks |
|------|----------|------------|----------------|
| **Storing all forecast data in entity attributes** | Database growth, slow queries, UI lag | Store forecast as separate sensor entities or use recorder exclude patterns | >48h forecast with 15-min resolution (~200 data points) |
| **No request timeout on external APIs** | Integration hangs indefinitely on network issues | Set timeout on all HTTP requests (default 10s); use aiohttp timeout parameter | First network glitch or slow API |
| **Creating entities in coordinator update** | Memory leaks, duplicate entities | Create entities ONCE during setup; update their data via coordinator | Multiple update cycles |
| **Logging full API responses at INFO level** | Log file bloat, disk space issues | Log at DEBUG level; log summary at INFO; use structured logging | Production deployment with verbose APIs |
| **Not implementing `always_update=False` for coordinator** | Excessive database writes | Enable when data supports equality checks (dataclass with `__eq__`) | Coordinator polling frequently with stable data |
| **Polling external API in sync with HA recorder** | Database write storms | Offset coordinator update from recorder commit intervals | High-frequency polling (< 30s intervals) |

---

## Security Mistakes

Domain-specific security issues beyond general web security.

| Mistake | Risk | Prevention |
|---------|------|------------|
| **Storing API tokens in plaintext in config entry data** | Token exposure in .storage/ files | Use config entry's `unique_id` as key; rely on HA's config entry encryption (HA 2024+) |
| **Not validating external API responses** | Code injection via malformed JSON/XML | Validate schema with pydantic/dataclasses; sanitize before state storage |
| **Exposing internal URLs in error messages** | Information disclosure in logs | Mask URLs in exceptions; log generic "API call failed" to user-facing errors |
| **Not implementing rate limiting on service calls** | DoS of external APIs; IP bans | Track call frequency; reject if exceeds limits; queue requests with backoff |
| **Trusting user-provided URLs in config flow** | SSRF attacks to internal network | Validate URL scheme (https only); block private IP ranges; use allow-list for known domains |
| **Not sanitizing device names from API** | XSS in frontend (entity names render in UI) | Strip HTML; limit character set; validate length |

---

## UX Pitfalls

Common user experience mistakes in this domain.

| Pitfall | User Impact | Better Approach |
|---------|-------------|-----------------|
| **No status sensor showing optimization state** | Users don't know if optimizer is working | Create diagnostic sensor showing: last run, next run, optimizer status |
| **Optimization failures don't update entity states** | Stale data shown as current | Set entities to "Unavailable" on coordinator failure; show age of data in attributes |
| **No way to manually trigger optimization** | Users can't test or force updates | Provide `homeassistant.update_entity` service support or custom "Run Optimization" button |
| **Energy forecast data not visualized** | Users can't see optimizer's plan | Provide forecast sensors compatible with ApexCharts or create custom card |
| **No indication when devices are offline** | Users automation fails silently | Set `available = False` when device unreachable; create binary_sensor for connectivity |
| **Generic error messages** | Users can't self-diagnose | Map common errors to user-friendly messages in strings.json; link to docs in error text |
| **No way to disable automation without removing integration** | Users can't temporarily pause | Provide switch entity to enable/disable optimization control |

---

## "Looks Done But Isn't" Checklist

Things that appear complete but are missing critical pieces.

- [ ] **Config Flow:** Often missing reauth flow—verify authentication failure triggers `async_step_reauth`
- [ ] **Config Flow:** Often missing unique_id abort check—verify `_abort_if_unique_id_configured()` called after discovery
- [ ] **Entities:** Often missing `available` property override—verify sets False when device unreachable
- [ ] **Entities:** Often missing `extra_state_attributes`—verify includes useful diagnostic info (last_update, source, etc.)
- [ ] **Coordinator:** Often missing `ConfigEntryAuthFailed` handling—verify auth failures trigger reauth not just log errors
- [ ] **Coordinator:** Often missing first refresh—verify `async_config_entry_first_refresh()` called before entity creation
- [ ] **Energy Sensors:** Often missing state_class or device_class—verify Energy Dashboard compatibility
- [ ] **Services:** Often missing schema validation—verify service YAML defines proper schemas with descriptions
- [ ] **Unload:** Often missing cleanup—verify `async_unload_entry` cancels tasks, closes sessions, unsubscribes listeners
- [ ] **Translation:** Often missing strings.json entries—verify all config flow steps, errors, entity names have translations
- [ ] **Testing:** Often missing coordinator failure tests—verify entities handle coordinator errors gracefully
- [ ] **Documentation:** Often missing example automations—verify README includes practical examples for common use cases

---

## Recovery Strategies

When pitfalls occur despite prevention, how to recover.

| Pitfall | Recovery Cost | Recovery Steps |
|---------|---------------|----------------|
| **Blocking operations detected** | LOW | Wrap in `async_add_executor_job`; redeploy; monitor logs for detection warnings |
| **Coordinator doesn't update entities** | LOW | Check `should_poll=False` on entities; verify `CoordinatorEntity` base class; ensure `async_request_refresh` called |
| **Entities missing unique_id** | MEDIUM | Add unique_id; create migration that maps old entity_id to new unique_id; document entity rename process |
| **Wrong state_class on sensors** | MEDIUM | Fix state_class; clear statistics DB for affected entities; may lose historical data—document migration |
| **Timezone-naive datetimes** | MEDIUM | Convert all datetime operations to use `dt_util`; test with multiple timezones; verify DST transitions |
| **MQTT → Native migration breaks entities** | HIGH | Preserve unique_id format from MQTT; create entity mapping tool; provide migration script; users may need manual reconfiguration |
| **Memory leaks from task/listener leaks** | MEDIUM | Implement proper `async_unload_entry`; track all `async_create_task` and `async_track_*` calls; cancel/remove on unload |
| **Duplicate config entries** | LOW | Implement unique_id in config flow; provide repair flow to merge duplicates (HA 2023.6+) |

---

## Pitfall-to-Phase Mapping

How roadmap phases should address these pitfalls.

| Pitfall | Prevention Phase | Verification |
|---------|------------------|--------------|
| Blocking operations in event loop | Phase 1: Architecture Foundation | Run integration; check logs for "Blocking call" warnings; verify HA UI stays responsive |
| Threading replacement misconceptions | Phase 1: Architecture Foundation | Reload integration multiple times; verify no task leaks; check `hass.async_create_task` used |
| DataUpdateCoordinator misuse | Phase 2: Data Coordination | Temporarily break API; verify entities become unavailable; verify recovery on API restore |
| Unique ID instability | Phase 3: Entity Structure | Restart HA; verify no duplicate entities; verify entity customizations persist |
| Config Flow validation gaps | Phase 4: Config Flow | Test with invalid credentials; test duplicate discovery; verify error messages user-friendly |
| Energy sensor state_class mistakes | Phase 3: Entity Structure | Check sensors appear in Energy Dashboard selector; verify statistics DB has data |
| Timezone misalignment | Phase 2: Data Coordination | Test with multiple timezones; test DST boundary dates; verify daily totals align with midnight |
| Entity properties doing I/O | Phase 3: Entity Structure | Profile property access; verify no network calls in getters; check performance |

---

## Phase-Specific Warnings

| Phase Topic | Likely Pitfall | Mitigation |
|-------------|---------------|------------|
| **Async Migration (Phase 1)** | Assuming `async def` wrapper makes sync code non-blocking | Audit all external calls: `requests` → `aiohttp`, file I/O → executor, sleep → `asyncio.sleep` |
| **Coordinator Setup (Phase 2)** | Not calling `async_config_entry_first_refresh` before entity creation | Follow exact pattern: coordinator init → first refresh → entity setup; test cold start |
| **Entity Creation (Phase 3)** | Forgetting `has_entity_name = True` for new integrations | Set in entity base class; required for modern integrations (Quality Scale Bronze) |
| **Config Flow (Phase 4)** | Missing version in manifest.json | HACS requires `version` key; Home Assistant requires `config_flow: true`; run `hassfest` validation |
| **HACS Packaging (Phase 5)** | Incorrect directory structure (multiple domains in custom_components/) | Only one domain per repo; must be `custom_components/{domain}/`; include `hacs.json` |
| **Testing (Phase 6)** | Not testing coordinator update failures | Mock API failures; verify entities set `available=False`; verify recovery on API restore |
| **Energy Integration (Phase 3)** | Mixing measurement and total state classes | Energy = `total_increasing`, Power = `measurement`; never use `measurement` for cumulative kWh |

---

## Sources

### Official Documentation (HIGH Confidence)
- [Blocking operations with asyncio | Home Assistant Developer Docs](https://developers.home-assistant.io/docs/asyncio_blocking_operations/)
- [Working with Async | Home Assistant Developer Docs](https://developers.home-assistant.io/docs/asyncio_working_with_async/)
- [Fetching data | Home Assistant Developer Docs](https://developers.home-assistant.io/docs/integration_fetching_data/)
- [Config flow | Home Assistant Developer Docs](https://developers.home-assistant.io/docs/config_entries_config_flow_handler/)
- [Entity | Home Assistant Developer Docs](https://developers.home-assistant.io/docs/core/entity/)
- [Sensor entity | Home Assistant Developer Docs](https://developers.home-assistant.io/docs/core/entity/sensor/)
- [Integration quality scale | Home Assistant Developer Docs](https://developers.home-assistant.io/docs/core/integration-quality-scale/)

### Community Resources (MEDIUM Confidence)
- [Home Assistant: Concurrency Model](https://www.thecandidstartup.org/2025/10/20/home-assistant-concurrency-model.html)
- [Use CoordinatorEntity with DataUpdateCoordinator - Automate The Things](https://aarongodfrey.dev/home%20automation/use-coordinatorentity-with-the-dataupdatecoordinator/)
- [Building a Home Assistant Custom Component Part 3: Config Flow](https://aarongodfrey.dev/home%20automation/building_a_home_assistant_custom_component_part_3/)

### Community Issues & Discussions (MEDIUM Confidence)
- [DataUpdateCoordinator-based integrations become unavailable after hours](https://community.home-assistant.io/t/dataupdatecoordinator-based-integrations-become-unavailable-after-a-few-hours/986502)
- [Energy Dashboard and timezones discussion](https://community.home-assistant.io/t/energy-dashboard-and-timezones/348218)
- [Entity is using state class 'measurement' impossible with device class 'energy'](https://github.com/home-assistant/core/issues/87376)
- [This entity does not have a unique ID - FAQ](https://www.home-assistant.io/faq/unique_id/)
- [HACS Integration Requirements](https://www.hacs.xyz/docs/publish/integration/)

### Observed Issues from Codebase Analysis (LOW-MEDIUM Confidence)
- EOS Connect codebase: Uses `requests` (sync), Flask (sync), threading, `pytz`, paho-mqtt (sync callbacks)
- Migration complexity: Flask → HA service layer, Threading → async tasks, MQTT sync → HA async MQTT
- Energy-specific: Time alignment for 15-min vs 1-hour optimization intervals, timezone handling across forecast APIs

---

*Pitfalls research for: Home Assistant Custom Integration (Energy Optimization)*
*Researched: 2026-02-14*
*Confidence: MEDIUM-HIGH (Official docs verified for core patterns; community reports inform edge cases; codebase analysis reveals migration-specific risks)*
