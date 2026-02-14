# Architecture Research

**Domain:** Home Assistant Custom Integration (Energy Optimization)
**Researched:** 2026-02-14
**Confidence:** HIGH

## Standard Architecture

### System Overview

```
┌─────────────────────────────────────────────────────────────┐
│                    Config Flow Layer                         │
│  ┌──────────────┐  ┌──────────────┐                          │
│  │ Config Flow  │  │ Options Flow │                          │
│  │ (initial)    │  │ (runtime)    │                          │
│  └──────┬───────┘  └──────┬───────┘                          │
│         │                 │                                   │
├─────────┴─────────────────┴───────────────────────────────────┤
│                    Integration Core                           │
│  ┌───────────────────────────────────────────────────────┐   │
│  │  __init__.py (async_setup_entry, async_unload_entry)  │   │
│  │  - Creates DataUpdateCoordinator                       │   │
│  │  - Forwards setup to platforms                         │   │
│  │  - Registers services                                  │   │
│  └───────────────┬───────────────────────────────────────┘   │
│                  │                                            │
├──────────────────┼────────────────────────────────────────────┤
│                  │     Coordinator Layer                      │
│  ┌───────────────┴────────────────────────────────────┐      │
│  │         DataUpdateCoordinator                       │      │
│  │  - Manages periodic polling                         │      │
│  │  - Fetches data from HA entities (hass.states)      │      │
│  │  - Calls external APIs                              │      │
│  │  - Notifies all subscribed entities                 │      │
│  └───────────────┬────────────────────────────────────┘      │
│                  │                                            │
├──────────────────┼────────────────────────────────────────────┤
│                  │     Entity Platforms                       │
│  ┌───────────────┴──────┐  ┌────────────┐  ┌─────────────┐  │
│  │    sensor.py         │  │ binary_    │  │  number.py  │  │
│  │ (CoordinatorEntity)  │  │ sensor.py  │  │             │  │
│  │ - Optimization data  │  │ - Status   │  │ - Settings  │  │
│  └──────────────────────┘  └────────────┘  └─────────────┘  │
├─────────────────────────────────────────────────────────────┤
│                    External Interfaces                        │
│  ┌──────────┐  ┌──────────┐  ┌──────────────────────────┐   │
│  │ HA State │  │ External │  │ Service Handlers          │   │
│  │ Machine  │  │ APIs     │  │ (override, force_update)  │   │
│  └──────────┘  └──────────┘  └──────────────────────────┘   │
└─────────────────────────────────────────────────────────────┘
```

### Component Responsibilities

| Component | Responsibility | Typical Implementation |
|-----------|----------------|------------------------|
| manifest.json | Declares integration metadata, dependencies, version | JSON file with domain, name, codeowners, iot_class, requirements |
| config_flow.py | Handles initial setup UI and runtime options changes | ConfigFlow + OptionsFlow classes with async_step_* methods |
| __init__.py | Entry point; creates coordinator, forwards to platforms, registers services | async_setup_entry, async_unload_entry, service registration |
| coordinator.py | Centralized data fetching and update coordination | DataUpdateCoordinator subclass with _async_update_data method |
| sensor.py / binary_sensor.py / number.py | Entity platforms exposing data to HA | CoordinatorEntity subclasses with properties returning coordinator data |
| services.yaml | Service action descriptions and schemas | YAML defining service parameters, descriptions, selectors |
| strings.json | All user-facing text for UI/errors/services | JSON with config, options, entity, services, exceptions sections |

## Recommended Project Structure

```
custom_components/
└── eos_ha/                # Integration domain name
    ├── manifest.json            # Integration metadata
    ├── __init__.py              # Integration setup/teardown
    ├── config_flow.py           # Config UI + Options UI
    ├── coordinator.py           # DataUpdateCoordinator subclass
    ├── const.py                 # Constants (DOMAIN, CONF_*, etc.)
    ├── sensor.py                # Sensor platform (optimization results)
    ├── binary_sensor.py         # Binary sensor platform (status indicators)
    ├── number.py                # Number platform (adjustable settings)
    ├── services.yaml            # Service definitions
    ├── strings.json             # English translations
    ├── translations/            # Translations for other languages
    │   └── en.json              # English (copy of strings.json)
    └── api/                     # Optional: API client wrappers
        ├── akkudoktor.py        # Akkudoktor API client
        └── eos_server.py        # EOS optimization server client
```

### Structure Rationale

- **manifest.json**: Required first file HA reads to identify integration
- **config_flow.py**: Modern integrations MUST use config flow (no YAML config)
- **coordinator.py**: Separate file keeps data fetching logic isolated from entity platforms
- **Platform files (sensor.py, etc.)**: One file per entity type; HA auto-discovers these
- **api/ directory**: Optional but recommended for clean separation of API client code
- **strings.json + translations/**: Required for all user-facing text to support i18n

## Architectural Patterns

### Pattern 1: DataUpdateCoordinator for Periodic Polling

**What:** Single coordinated polling across all entities to prevent redundant API calls

**When to use:** When integration needs to fetch data periodically (every N minutes) and multiple entities consume that data

**Trade-offs:**
- **Pro:** Efficient (single API call for all entities), built-in error handling, entities auto-update
- **Pro:** Automatic availability management (entities marked unavailable if coordinator fails)
- **Con:** All entities update at same interval (can't have different polling rates)

**Example:**
```python
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

class EOSCoordinator(DataUpdateCoordinator):
    """Coordinate fetching EOS optimization data."""

    def __init__(self, hass, api_client):
        """Initialize coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            name="EOS HA",
            update_interval=timedelta(minutes=15),
        )
        self.api_client = api_client

    async def _async_update_data(self):
        """Fetch data from HA entities and external APIs."""
        try:
            # 1. Read HA entity states
            price_state = self.hass.states.get("sensor.electricity_price")
            soc_state = self.hass.states.get("sensor.battery_soc")

            # 2. Call external APIs
            pv_forecast = await self.api_client.get_pv_forecast()
            optimization = await self.api_client.optimize(
                price=float(price_state.state),
                soc=float(soc_state.state),
                forecast=pv_forecast
            )

            # 3. Return data for entities to consume
            return {
                "optimization": optimization,
                "pv_forecast": pv_forecast,
                "last_update": dt.utcnow(),
            }
        except ApiError as err:
            raise UpdateFailed(f"Error communicating with API: {err}")
```

### Pattern 2: CoordinatorEntity for Entity Platforms

**What:** Base class for entities that subscribe to DataUpdateCoordinator updates

**When to use:** Every entity that consumes coordinator data (sensor, binary_sensor, number, etc.)

**Trade-offs:**
- **Pro:** Automatic subscription/unsubscription, automatic availability, should_poll=False
- **Pro:** Calls async_write_ha_state() automatically when coordinator updates
- **Con:** Entity must pull data from coordinator.data (not pushed directly)

**Example:**
```python
from homeassistant.components.sensor import SensorEntity
from homeassistant.helpers.update_coordinator import CoordinatorEntity

class EOSOptimizationSensor(CoordinatorEntity, SensorEntity):
    """Sensor exposing optimization results."""

    def __init__(self, coordinator, entity_description):
        """Initialize sensor."""
        super().__init__(coordinator)
        self.entity_description = entity_description
        self._attr_unique_id = f"eos_{entity_description.key}"

    @property
    def native_value(self):
        """Return sensor value from coordinator data."""
        # Pull data from coordinator.data (set by _async_update_data)
        return self.coordinator.data["optimization"].get(
            self.entity_description.key
        )

    @property
    def available(self):
        """Return if entity is available."""
        # Automatic: True if coordinator.last_update_success, False otherwise
        return self.coordinator.last_update_success
```

### Pattern 3: Config Flow + Options Flow

**What:** UI-based configuration (replaces YAML configuration)

**When to use:** Always for modern integrations (YAML config is deprecated)

**Trade-offs:**
- **Pro:** User-friendly, validates input, supports discovery
- **Pro:** Can modify settings at runtime without restart (via Options Flow)
- **Con:** More code than YAML config (but required for quality integrations)

**Example:**
```python
from homeassistant import config_entries
from homeassistant.core import callback
import voluptuous as vol

class EOSConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle config flow for EOS HA."""

    VERSION = 1

    async def async_step_user(self, user_input=None):
        """Handle initial setup step."""
        errors = {}

        if user_input is not None:
            # Validate API connection
            try:
                await validate_api(user_input[CONF_API_URL])
                return self.async_create_entry(
                    title="EOS HA",
                    data=user_input
                )
            except CannotConnect:
                errors["base"] = "cannot_connect"

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema({
                vol.Required(CONF_API_URL): str,
                vol.Optional(CONF_UPDATE_INTERVAL, default=15): int,
            }),
            errors=errors,
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        """Get the options flow handler."""
        return EOSOptionsFlow(config_entry)

class EOSOptionsFlow(config_entries.OptionsFlow):
    """Handle options flow (runtime configuration changes)."""

    async def async_step_init(self, user_input=None):
        """Manage options."""
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema({
                vol.Optional(
                    CONF_UPDATE_INTERVAL,
                    default=self.config_entry.options.get(CONF_UPDATE_INTERVAL, 15)
                ): int,
            }),
        )
```

### Pattern 4: Platform Setup via async_forward_entry_setups

**What:** Forward config entry to entity platforms (sensor, binary_sensor, etc.)

**When to use:** When integration exposes multiple entity types

**Trade-offs:**
- **Pro:** Clean separation of concerns (each platform in its own file)
- **Pro:** HA auto-discovers platform files by name
- **Con:** Must implement async_setup_entry in each platform file

**Example in __init__.py:**
```python
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant

PLATFORMS = [Platform.SENSOR, Platform.BINARY_SENSOR, Platform.NUMBER]

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up EOS HA from config entry."""
    # 1. Create coordinator
    coordinator = EOSCoordinator(hass, entry.data)

    # 2. First refresh to populate data
    await coordinator.async_config_entry_first_refresh()

    # 3. Store coordinator in hass.data
    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = coordinator

    # 4. Forward to platforms
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    # 5. Register update listener for options flow changes
    entry.async_on_unload(entry.add_update_listener(update_listener))

    return True

async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload config entry."""
    # Unload platforms
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)

    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok
```

**Example in sensor.py:**
```python
async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up sensor platform from config entry."""
    coordinator = hass.data[DOMAIN][entry.entry_id]

    entities = [
        EOSOptimizationSensor(coordinator, description)
        for description in SENSOR_DESCRIPTIONS
    ]

    async_add_entities(entities)
```

### Pattern 5: Service Registration in async_setup

**What:** Register custom service actions at integration level

**When to use:** When integration needs callable actions (e.g., manual triggers, overrides)

**Trade-offs:**
- **Pro:** Services can be called from automations, scripts, developer tools
- **Pro:** Schema validation built-in
- **Con:** Must register in async_setup (NOT async_setup_entry) to ensure availability

**Example:**
```python
async def async_setup(hass: HomeAssistant, config: dict) -> bool:
    """Set up the EOS HA component (registers services)."""

    async def handle_force_update(call):
        """Handle force update service call."""
        # Get coordinator from first config entry
        entry_id = list(hass.data[DOMAIN].keys())[0]
        coordinator = hass.data[DOMAIN][entry_id]
        await coordinator.async_request_refresh()

    hass.services.async_register(
        DOMAIN,
        "force_update",
        handle_force_update,
        schema=vol.Schema({}),
    )

    return True
```

**Corresponding services.yaml:**
```yaml
force_update:
  name: Force optimization update
  description: Triggers an immediate optimization cycle
  fields: {}
```

### Pattern 6: Reading Other HA Entities (Input Pattern)

**What:** Access state of other HA entities as inputs to integration logic

**When to use:** When integration needs to consume data from other integrations (prices, SOC, consumption)

**Trade-offs:**
- **Pro:** Simple API (hass.states.get), works with any entity
- **Pro:** Can listen for state changes with event listeners
- **Con:** Returns None if entity doesn't exist (must handle gracefully)
- **Con:** State is string; must convert to appropriate type

**Example:**
```python
async def _async_update_data(self):
    """Fetch data from HA entities and external APIs."""
    # Read entity states
    price_state = self.hass.states.get("sensor.electricity_price")
    soc_state = self.hass.states.get("sensor.battery_soc")
    consumption_state = self.hass.states.get("sensor.home_consumption")

    # Handle missing entities
    if not price_state or not soc_state:
        raise UpdateFailed("Required sensors not available")

    # Convert state strings to appropriate types
    try:
        price = float(price_state.state)
        soc = float(soc_state.state)
        consumption = float(consumption_state.state) if consumption_state else 0
    except ValueError as err:
        raise UpdateFailed(f"Invalid sensor state: {err}")

    # Use states in optimization
    optimization = await self.api_client.optimize(
        price=price,
        soc=soc,
        consumption=consumption,
    )

    return {"optimization": optimization}
```

**Alternative: State change listeners:**
```python
async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up with state listeners."""
    coordinator = EOSCoordinator(hass, entry.data)

    async def _handle_state_change(event):
        """Trigger coordinator refresh when input entities change."""
        await coordinator.async_request_refresh()

    # Listen for specific entity state changes
    entry.async_on_unload(
        hass.bus.async_listen(
            "state_changed",
            _handle_state_change,
            event_filter=lambda e: e.data["entity_id"] in [
                "sensor.electricity_price",
                "sensor.battery_soc",
            ]
        )
    )

    # ... rest of setup
```

## Data Flow

### Request Flow: Periodic Optimization Cycle

```
[Timer Triggers]
    ↓
[DataUpdateCoordinator._async_update_data]
    ↓
    ├── Read HA States → hass.states.get("sensor.price")
    ├── Call External API → Akkudoktor PV Forecast
    └── Call External API → EOS Optimization Server
            ↓
    [Coordinator stores data in self.data]
            ↓
    [Coordinator notifies all CoordinatorEntity instances]
            ↓
    [Each entity reads coordinator.data and updates]
            ↓
    [Entities call async_write_ha_state()]
            ↓
    [HA State Machine updates]
            ↓
    [Frontend displays new values]
```

### Configuration Flow

```
[User clicks Add Integration]
    ↓
[ConfigFlow.async_step_user]
    ↓ (user enters API URL, interval)
[Validate API connection]
    ↓
[Create config entry] → [async_setup_entry called]
    ↓
[Create DataUpdateCoordinator]
    ↓
[First refresh: async_config_entry_first_refresh]
    ↓
[Forward to platforms: async_forward_entry_setups]
    ↓
[Register services: hass.services.async_register]
    ↓
[Integration ready]
```

### Options Flow (Runtime Config Changes)

```
[User clicks Configure on integration card]
    ↓
[OptionsFlow.async_step_init]
    ↓ (user changes update interval)
[Update config_entry.options]
    ↓
[update_listener callback triggered]
    ↓
[Update coordinator.update_interval]
    ↓
[Coordinator uses new interval for next update]
```

### Service Call Flow

```
[Automation/Script calls eos_ha.force_update]
    ↓
[Service handler receives call]
    ↓
[Retrieve coordinator from hass.data]
    ↓
[Call coordinator.async_request_refresh()]
    ↓
[Coordinator immediately runs _async_update_data]
    ↓
[Normal data flow continues...]
```

## Anti-Patterns

### Anti-Pattern 1: Polling in Entity Properties

**What people do:** Call APIs or do I/O in entity property getters
```python
# BAD
@property
def native_value(self):
    """This blocks the event loop!"""
    response = requests.get("https://api.example.com/data")  # Blocking I/O!
    return response.json()["value"]
```

**Why it's wrong:**
- Blocks the event loop
- Called frequently by frontend (can hammer APIs)
- No error handling or coordination
- Multiple entities = multiple simultaneous API calls

**Do this instead:** Use DataUpdateCoordinator
```python
# GOOD
@property
def native_value(self):
    """Return cached value from coordinator."""
    return self.coordinator.data["optimization"]["value"]

# API call happens in coordinator._async_update_data (async, coordinated)
```

### Anti-Pattern 2: Registering Services in async_setup_entry

**What people do:** Register services in async_setup_entry or platform setup

**Why it's wrong:**
- Services disappear when config entry unloaded/reloaded
- Services unavailable until user adds integration
- Can't validate automations referencing the service

**Do this instead:** Register in async_setup (integration level)
```python
# GOOD - in __init__.py
async def async_setup(hass: HomeAssistant, config: dict) -> bool:
    """Register services at integration level."""
    hass.services.async_register(DOMAIN, "force_update", handle_force_update)
    return True
```

### Anti-Pattern 3: YAML Configuration

**What people do:** Add `configuration.yaml` support instead of config flow

**Why it's wrong:**
- Deprecated pattern (all modern integrations use config flow)
- Can't change config without restarting HA
- No validation until restart (bad UX)
- Won't be accepted into HACS/core

**Do this instead:** Implement ConfigFlow (see Pattern 3)

### Anti-Pattern 4: Not Handling Missing Entities Gracefully

**What people do:** Assume input entities always exist
```python
# BAD
price = float(self.hass.states.get("sensor.price").state)  # Crashes if None!
```

**Why it's wrong:**
- Crashes integration if user hasn't configured required sensors
- No helpful error message
- Integration becomes unavailable

**Do this instead:** Check for None and raise UpdateFailed with clear message
```python
# GOOD
price_state = self.hass.states.get("sensor.price")
if not price_state or price_state.state in ["unavailable", "unknown"]:
    raise UpdateFailed(
        "sensor.price is not available. Please configure a price sensor."
    )
try:
    price = float(price_state.state)
except ValueError:
    raise UpdateFailed(f"Invalid price value: {price_state.state}")
```

### Anti-Pattern 5: Creating Coordinator per Entity

**What people do:** Each entity creates its own coordinator/API client

**Why it's wrong:**
- Defeats the purpose of coordination (multiple API calls)
- Wastes resources (multiple timers, connections)
- Entities can show inconsistent data (fetched at different times)

**Do this instead:** One coordinator shared by all entities (see Pattern 1)

## Integration Points

### External Services

| Service | Integration Pattern | Notes |
|---------|---------------------|-------|
| Home Assistant State Machine | `hass.states.get(entity_id)` | Returns State object or None; state is string |
| Akkudoktor PV Forecast API | Async HTTP client (aiohttp) | Called from coordinator._async_update_data |
| EOS Optimization Server | Async HTTP client (aiohttp) | Called from coordinator._async_update_data |

### Internal Boundaries

| Boundary | Communication | Notes |
|----------|---------------|-------|
| __init__.py ↔ Coordinator | Direct instantiation | Coordinator stored in hass.data[DOMAIN][entry_id] |
| Coordinator ↔ Entities | Observer pattern | Entities subscribe via CoordinatorEntity, pull data from coordinator.data |
| Config Flow ↔ Integration | Config entry creation | Config flow creates entry → triggers async_setup_entry |
| Options Flow ↔ Coordinator | Update listener callback | Options changes → update_listener → update coordinator properties |
| Services ↔ Coordinator | Via hass.data lookup | Service handler retrieves coordinator from hass.data |

## Build Order and Dependencies

### Recommended Build Sequence

The following order minimizes refactoring and allows incremental testing:

**Phase 1: Foundation**
1. **manifest.json** — Required first (HA won't load integration without it)
2. **const.py** — Define constants before using them
3. **__init__.py (minimal)** — Stub async_setup and async_setup_entry (return True)
4. **strings.json (minimal)** — At least title and config section

**Phase 2: Configuration**
5. **config_flow.py** — ConfigFlow with async_step_user (even if just asking for confirmation)
   - Test: Integration appears in Add Integration UI
   - Test: Can add integration (even if it does nothing yet)

**Phase 3: Data Layer**
6. **coordinator.py** — DataUpdateCoordinator with _async_update_data
   - Initially return hardcoded data
   - Test: Coordinator refreshes on interval
7. **Update __init__.py** — Create coordinator, call async_config_entry_first_refresh
   - Test: Integration sets up without errors

**Phase 4: First Entity Platform**
8. **sensor.py** — SensorEntity + CoordinatorEntity for one sensor
   - Test: Sensor appears in HA, shows data from coordinator
   - Test: Sensor updates when coordinator updates

**Phase 5: Additional Platforms**
9. **binary_sensor.py** — Status/warning binary sensors
10. **number.py** — Adjustable settings (if needed)
    - Test: All entities appear and update

**Phase 6: Features**
11. **services.yaml + service handlers** — Force update, override services
    - Test: Services appear in Developer Tools
    - Test: Calling service triggers expected behavior
12. **Options Flow** — Runtime configuration changes
    - Test: Can modify settings without removing integration

**Phase 7: Polish**
13. **Complete strings.json** — All translations, error messages
14. **Error handling** — Graceful degradation, helpful error messages
15. **API clients (api/ directory)** — Wrap external API calls cleanly

### Dependency Graph

```
manifest.json (no dependencies)
    ↓
const.py (no dependencies)
    ↓
coordinator.py (depends on: const.py, api clients)
    ↓
__init__.py (depends on: const.py, coordinator.py)
    ↓
    ├── sensor.py (depends on: const.py, coordinator.py)
    ├── binary_sensor.py (depends on: const.py, coordinator.py)
    └── number.py (depends on: const.py, coordinator.py)

config_flow.py (depends on: const.py, optionally api clients for validation)
services.yaml (no code dependencies)
strings.json (no code dependencies)
```

### Why This Order?

1. **Manifest first**: HA won't recognize integration without it
2. **Config flow early**: Modern integrations require it; validates setup works
3. **Coordinator before entities**: Entities depend on coordinator; build bottom-up
4. **One platform at a time**: Get pattern working once, then replicate
5. **Services last**: Requires working coordinator and entities to be useful
6. **Polish last**: Core functionality must work before refining UX

## Sources

**HIGH Confidence (Official Documentation):**
- [Integration architecture | Home Assistant Developer Docs](https://developers.home-assistant.io/docs/architecture_components/)
- [Fetching data | Home Assistant Developer Docs](https://developers.home-assistant.io/docs/integration_fetching_data/)
- [Config entries | Home Assistant Developer Docs](https://developers.home-assistant.io/docs/config_entries_index/)
- [Options flow | Home Assistant Developer Docs](https://developers.home-assistant.io/docs/config_entries_options_flow_handler/)
- [Integration file structure | Home Assistant Developer Docs](https://developers.home-assistant.io/docs/creating_integration_file_structure/)
- [Integration manifest | Home Assistant Developer Docs](https://developers.home-assistant.io/docs/creating_integration_manifest/)
- [Binary sensor entity | Home Assistant Developer Docs](https://developers.home-assistant.io/docs/core/entity/binary-sensor/)
- [Integration service actions | Home Assistant Developer Docs](https://developers.home-assistant.io/docs/dev_101_services/)
- [Backend localization | Home Assistant Developer Docs](https://developers.home-assistant.io/docs/internationalization/core/)

**MEDIUM Confidence (Community Resources, 2024-2026):**
- [Building a Home Assistant Custom Component Part 1 - Automate The Things](https://aarongodfrey.dev/home%20automation/building_a_home_assistant_custom_component_part_1/)
- [Building a Home Assistant Custom Component Part 3: Config Flow - Automate The Things](https://aarongodfrey.dev/home%20automation/building_a_home_assistant_custom_component_part_3/)
- [Use CoordinatorEntity when using the DataUpdateCoordinator - Automate The Things](https://aarongodfrey.dev/home%20automation/use-coordinatorentity-with-the-dataupdatecoordinator/)
- [Writing a Home Assistant Core Integration: Part 2 · Jon Seager](https://jnsgr.uk/2024/10/writing-a-home-assistant-integration/)
- [HACS Integration Publishing | HACS](https://www.hacs.xyz/docs/publish/integration/)
- [EMHASS: Energy Management for Home Assistant | GitHub](https://github.com/davidusb-geek/emhass)
- [Modern HA Integration Blueprint | GitHub](https://github.com/jpawlowski/hacs.integration_blueprint)

---
*Architecture research for: EOS HA Home Assistant Integration*
*Researched: 2026-02-14*
