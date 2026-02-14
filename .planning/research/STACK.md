# Technology Stack

**Project:** EOS Connect Home Assistant Integration
**Researched:** 2026-02-14
**Confidence:** HIGH

## Recommended Stack

### Core Framework

| Technology | Version | Purpose | Why |
|------------|---------|---------|-----|
| Python | >=3.13.2 | Runtime environment | Home Assistant 2026 requires Python >=3.13.2. Python 3.12 is no longer supported. Use 3.13 or 3.14. |
| Home Assistant Core | >=2026.1.0 | Integration framework | Target the latest stable HA release for async patterns, DataUpdateCoordinator improvements, and modern config flow features. |
| asyncio | stdlib | Async runtime | Built-in async/await support. All HA integrations must be fully async to avoid blocking the event loop. |

### Data Management

| Technology | Version | Purpose | Why |
|------------|---------|---------|-----|
| DataUpdateCoordinator | homeassistant.helpers | Centralized data fetching | Standard pattern for managing periodic updates across multiple entities. Handles rate limiting, error recovery, and prevents duplicate API calls. |
| CoordinatorEntity | homeassistant.helpers | Entity base class | Automatically handles `should_poll=False`, `async_update()`, and coordinator subscriptions. Use instead of raw Entity class. |
| RestoreSensor/RestoreNumber | homeassistant.helpers | State persistence | Restore entity states after HA restart. Call `await self.async_get_last_sensor_data()` or `async_get_last_number_data()` in `async_added_to_hass()`. |

### HTTP Client

| Technology | Version | Purpose | Why |
|------------|---------|---------|-----|
| aiohttp | >=3.13.3 | Async HTTP client | Standard for HA integrations. Use `async_get_clientsession(hass)` from `homeassistant.helpers.aiohttp_client` for connection pooling and proper lifecycle management. Home Assistant 2026.1 uses aiohttp 3.13.3. |
| async_timeout | stdlib (asyncio) | Request timeouts | Wrap HTTP calls in `async with asyncio.timeout(10)` to prevent hanging requests. The standalone `async_timeout` package is deprecated—use stdlib `asyncio.timeout()` instead. |

**Alternative:** httpx (via `get_async_client(hass)`) supports both sync and async, but aiohttp is more common in HA ecosystem and has better integration with HA's lifecycle.

### Schema Validation

| Technology | Version | Purpose | Why |
|------------|---------|---------|-----|
| voluptuous | (HA dependency) | Config/Options Flow schemas | Standard for data entry flow validation. Use `vol.Schema()` with `vol.Required()` and `vol.Optional()` for user input validation in config flow steps. |
| Home Assistant CV | homeassistant.helpers.config_validation | HA-specific validators | Provides validators for common HA types (entity IDs, time periods, etc.). Import as `cv`. |

### Entity Platforms

| Technology | Version | Purpose | Why |
|------------|---------|---------|-----|
| SensorEntity | homeassistant.components.sensor | Read-only numeric/text data | For energy prices, optimization results, forecasts. Use `native_value`, `native_unit_of_measurement`, `device_class`, and `state_class` properties. |
| BinarySensorEntity | homeassistant.components.binary_sensor | Boolean state sensors | For optimization status, connection health. Use `is_on` property and `device_class` for semantic meaning. |
| NumberEntity | homeassistant.components.number | User-adjustable numeric values | For configuration parameters (min SOC, max charge rate). Implement `async_set_native_value()` and define `native_min_value`, `native_max_value`, `native_step`. |

### Configuration & Versioning

| Technology | Version | Purpose | Why |
|------------|---------|---------|-----|
| ConfigFlow | homeassistant.config_entries | UI-based setup | Required for HACS compatibility. Set `"config_flow": true` in manifest.json. Implement `async_step_user()` and optionally `async_step_reconfigure()` for credential refresh. |
| OptionsFlow | homeassistant.config_entries | UI-based options | For runtime configuration changes without re-adding integration. Implement `async_get_options_flow()` in ConfigFlow class. |
| AwesomeVersion | (HA dependency) | Version parsing | Required for manifest.json `version` field. Use SemVer (e.g., `1.0.0`) or CalVer (e.g., `2026.2.0`) format. HACS validates this. |

### Testing

| Technology | Version | Purpose | Why |
|------------|---------|---------|-----|
| pytest | latest | Test framework | Standard for HA integrations. Run `pytest tests/components/your_domain/ --cov=custom_components.your_domain --cov-report term-missing -vv` |
| pytest-homeassistant-custom-component | 0.13.313+ | HA test fixtures | Extracts test fixtures from HA Core daily. Provides `hass` fixture, mock config entries, and HA testing utilities. Version 0.13.313 matches HA 2026.2.0. |
| pytest-asyncio | latest | Async test support | For testing async functions. Use `@pytest.mark.asyncio` decorator. |
| pytest-cov | latest | Coverage reporting | For tracking test coverage. Integrated with pytest. |

### Development Tools

| Technology | Version | Purpose | Why |
|------------|---------|---------|-----|
| Ruff | 0.15.1+ | Linting and formatting | HA uses Ruff for code checking and formatting. Replaces autoflake, pyupgrade, flake8. Run `ruff check .` and `ruff format .`. |
| Mypy | latest | Static type checking | Required by HA quality standards. Add type hints to all functions. Run via pre-commit or `mypy custom_components/`. |
| Pre-commit | latest | Git hook management | Automates linting before commits. HA uses pre-commit for Ruff, Mypy, Codespell, Yamllint, Prettier. Copy `.pre-commit-config.yaml` from HA core or blueprint repo. |
| Codespell | 2.4.1+ | Spell checking | Catches typos in code and docs. Part of HA's pre-commit pipeline. |
| Yamllint | 1.37.1+ | YAML validation | Validates `manifest.json`, `services.yaml`, and translation files. |

### Supporting Libraries (Optional)

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| pydantic | 2.x | Data modeling | If you need complex data validation beyond voluptuous. HA is moving toward this for some integrations. |
| open-meteo-solar-forecast | 0.1.22+ | PV forecasting | Already in existing requirements.txt. Keep for Akkudoktor API integration. |
| packaging | >=23.2 | Version parsing | For comparing HA versions or integration versions in code. |

## Alternatives Considered

| Category | Recommended | Alternative | Why Not |
|----------|-------------|-------------|---------|
| HTTP Client | aiohttp | httpx | httpx supports both sync and async, but aiohttp is more common in HA ecosystem. HA provides better helpers for aiohttp (`async_get_clientsession`). |
| HTTP Client | aiohttp | requests | requests is synchronous only. Blocks event loop. Never use in HA integrations. |
| Timeout | asyncio.timeout() | async_timeout package | async_timeout is deprecated. Python 3.11+ includes `asyncio.timeout()` in stdlib. |
| Entity Base | CoordinatorEntity | Entity | CoordinatorEntity automatically handles coordinator subscriptions and sets `should_poll=False`. Always use for coordinator-based entities. |
| Config | ConfigFlow | YAML in configuration.yaml | YAML config is legacy. HACS requires ConfigFlow. Users expect UI-based setup. |
| Testing | pytest-homeassistant-custom-component | Manual HA fixtures | This package extracts all HA test fixtures automatically. Updates daily. Saves hundreds of lines of boilerplate. |
| Linting | Ruff | Black + flake8 + autoflake | HA consolidated to Ruff for speed. Ruff is 10-100x faster and replaces multiple tools. |

## What NOT to Use

| Avoid | Why | Use Instead |
|-------|-----|-------------|
| requests | Synchronous HTTP library blocks event loop | aiohttp with `async_get_clientsession(hass)` |
| time.sleep() | Blocks event loop | `await asyncio.sleep()` |
| threading | Causes deadlocks, race conditions | `hass.async_add_executor_job()` for CPU-bound work |
| async_timeout package | Deprecated, will be removed | `asyncio.timeout()` (stdlib since Python 3.11) |
| ConfigEntry.options.setdefault() | Direct dict mutation | Create new dict and call `hass.config_entries.async_update_entry()` |
| Entity.update() | Synchronous, blocks event loop | `async_update()` or DataUpdateCoordinator |
| hass.states.set() | Synchronous | `hass.states.async_set()` |
| Global state/singletons | Not thread-safe, causes issues with multiple entries | Store state in `hass.data[DOMAIN][entry.entry_id]` |
| Bare except: | Hides errors, fails silently | Catch specific exceptions (`UpdateFailed`, `ConfigEntryAuthFailed`) |

## Stack Patterns by Variant

**If integration polls an API (like EOS optimization server):**
- Use DataUpdateCoordinator with `update_interval=timedelta(minutes=5)` (or appropriate interval)
- Set `always_update=False` if your data classes implement `__eq__` for efficient change detection
- Raise `UpdateFailed` for API errors, `ConfigEntryAuthFailed` for auth failures
- Wrap API calls in `async with asyncio.timeout(10)` to prevent hangs

**If integration receives push updates:**
- Use DataUpdateCoordinator with `update_interval=None`
- Call `coordinator.async_set_updated_data(data)` when push data arrives
- Still implement `_async_update_data()` for initial data fetch on startup

**If integration controls devices (like inverters):**
- Register services in `async_setup()` using `hass.services.async_register()`
- Use `services.yaml` to document service parameters
- Validate service data with voluptuous schemas
- For entity-level services, use `async_register_platform_entity_service()`

**If integration exposes user-configurable parameters:**
- Use NumberEntity with `async_set_native_value()` for numeric settings
- Store settings in ConfigEntry.options via OptionsFlow
- Trigger coordinator refresh when settings change: `await coordinator.async_request_refresh()`

## Version Compatibility

| Package | Compatible With | Notes |
|---------|-----------------|-------|
| pytest-homeassistant-custom-component | Home Assistant version | Package version (e.g., 0.13.313) matches HA release (2026.2.0). Update regularly. |
| Python 3.13 | Home Assistant 2026.x | Python 3.14 also supported as of HA 2026.1 |
| aiohttp 3.13.3+ | Home Assistant 2026.1+ | HA ships with specific aiohttp version. Use what's in HA's requirements. |
| Ruff 0.15.1+ | Pre-commit config | Match version in HA's `.pre-commit-config.yaml` for consistency |

## Manifest.json Requirements (HACS)

**Required fields:**
```json
{
  "domain": "eos_connect",
  "name": "EOS Connect",
  "version": "1.0.0",
  "documentation": "https://github.com/yourusername/eos_connect",
  "issue_tracker": "https://github.com/yourusername/eos_connect/issues",
  "codeowners": ["@yourusername"],
  "config_flow": true,
  "dependencies": [],
  "requirements": ["aiohttp>=3.13.3", "open-meteo-solar-forecast>=0.1.22"],
  "iot_class": "cloud_polling",
  "integration_type": "hub"
}
```

**Version format:** Use SemVer (`1.0.0`, `1.2.3`) or CalVer (`2026.2.0`). Must be recognized by AwesomeVersion.

**Dependencies:** Only list built-in HA integrations (e.g., `["http"]`). Don't list custom integrations here.

**Requirements:** Python packages from PyPI. Use `>=` for minimum version. HA will install these automatically.

**HACS additional requirements:**
- Only one integration per repository
- Integration must be in `custom_components/<domain>/` directory
- Must be registered in [home-assistant/brands](https://github.com/home-assistant/brands) repository for UI assets
- Publish GitHub releases for version tracking (HACS shows 5 most recent releases)

## Repository Structure

```
custom_components/eos_connect/
├── __init__.py              # Integration setup, coordinator initialization
├── manifest.json            # Integration metadata (see above)
├── config_flow.py           # UI-based configuration
├── const.py                 # Constants (DOMAIN, DEFAULT_*, CONF_*)
├── coordinator.py           # DataUpdateCoordinator implementation
├── sensor.py                # SensorEntity platform
├── binary_sensor.py         # BinarySensorEntity platform
├── number.py                # NumberEntity platform
├── services.yaml            # Service action documentation
├── strings.json             # UI text translations (config flow, entities)
├── translations/
│   └── en.json              # English translations (mirrors strings.json)
└── icons/
    └── eos_connect.png      # Integration icon (optional, use brands repo instead)
```

## Installation (Development)

```bash
# Core dependencies (for integration development)
# These are provided by Home Assistant runtime, not directly installed

# Development dependencies
pip install pytest pytest-asyncio pytest-cov
pip install pytest-homeassistant-custom-component>=0.13.313
pip install pre-commit ruff mypy

# Project-specific dependencies (add to manifest.json requirements)
# aiohttp>=3.13.3  (use HA's built-in session)
# open-meteo-solar-forecast>=0.1.22
# packaging>=23.2
```

## Migration Notes (Docker → HA Integration)

**Remove from requirements.txt:**
- Flask (HA provides web interface)
- gevent (HA uses asyncio, not gevent)
- paho-mqtt (use HA's MQTT integration if needed)
- psutil (HA provides system monitoring)
- pandas/numpy (avoid heavy deps; process data in optimization server, not HA)

**Keep:**
- open-meteo-solar-forecast (for Akkudoktor API)
- packaging (if needed for version checks)

**Replace:**
- requests → aiohttp via `async_get_clientsession(hass)`
- PyYAML/ruamel.yaml → ConfigEntry storage (structured data in HA's database)
- Flask endpoints → HA services registered via `hass.services.async_register()`

**Async conversion:**
- All functions must be `async def` with `await` for I/O
- No blocking calls (no `requests.get()`, `time.sleep()`, `open()` without executor)
- Use `hass.async_add_executor_job(sync_function)` for unavoidable sync code

## Sources

### High Confidence (Official Documentation)
- [Integration Manifest](https://developers.home-assistant.io/docs/creating_integration_manifest/) — manifest.json structure and requirements
- [Fetching Data (DataUpdateCoordinator)](https://developers.home-assistant.io/docs/integration_fetching_data/) — coordinator patterns, polling vs push, error handling
- [Config Flow](https://developers.home-assistant.io/docs/config_entries_config_flow_handler/) — config flow and options flow implementation
- [Binary Sensor Entity](https://developers.home-assistant.io/docs/core/entity/binary-sensor/) — BinarySensorEntity implementation
- [Sensor Entity](https://developers.home-assistant.io/docs/core/entity/sensor/) — SensorEntity, state classes, device classes, units
- [Number Entity](https://developers.home-assistant.io/docs/core/entity/number/) — NumberEntity implementation, min/max/step handling
- [Integration Service Actions](https://developers.home-assistant.io/docs/dev_101_services/) — service registration and schemas
- [Working with Async](https://developers.home-assistant.io/docs/asyncio_working_with_async/) — async best practices, executor patterns
- [Testing Your Code](https://developers.home-assistant.io/docs/development_testing/) — pytest and testing framework
- [Inject Websession](https://developers.home-assistant.io/docs/core/integration-quality-scale/rules/inject-websession/) — aiohttp session injection

### High Confidence (HACS Official)
- [HACS Integration Requirements](https://www.hacs.xyz/docs/publish/integration/) — repository structure, manifest requirements, versioning

### Medium Confidence (GitHub Official)
- [HA Core Pre-commit Config](https://github.com/home-assistant/core/blob/dev/.pre-commit-config.yaml) — current linting tool versions

### Medium Confidence (PyPI Official)
- [homeassistant on PyPI](https://pypi.org/project/homeassistant/) — Python version requirements (>=3.13.2 for HA 2026)
- [pytest-homeassistant-custom-component](https://github.com/MatthewFlamm/pytest-homeassistant-custom-component) — test fixture extraction

### Medium Confidence (Community Resources)
- [Building HA Custom Component Series](https://aarongodfrey.dev/home%20automation/building_a_home_assistant_custom_component_part_1/) — practical implementation guide
- [Writing HA Integrations](https://samrambles.com/guides/writing-home-assistant-integrations/index.html) — architecture patterns

---
*Stack research for: Home Assistant Custom Integration (Energy Optimization)*
*Researched: 2026-02-14*
*Next: Create FEATURES.md, ARCHITECTURE.md, PITFALLS.md*
