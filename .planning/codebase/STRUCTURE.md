# Codebase Structure

**Analysis Date:** 2026-02-14

## Directory Layout

```
eos-ha/
├── src/                           # Core application
│   ├── eos_ha.py             # Main orchestration engine + Flask web server
│   ├── config.py                  # Configuration management
│   ├── log_handler.py             # In-memory logging for web dashboard
│   ├── version.py                 # Version string
│   ├── constants.py               # Currency mappings
│   ├── interfaces/                # Pluggable adapters for external systems
│   │   ├── base_control.py        # Core state machine (7 control modes)
│   │   ├── load_interface.py      # Consumption data (HA, OpenHAB, static)
│   │   ├── battery_interface.py   # SOC and dynamic charge limits
│   │   ├── battery_price_handler.py # Battery cost calculation
│   │   ├── price_interface.py     # Electricity prices (Tibber, Stromligning, etc)
│   │   ├── pv_interface.py        # PV forecasts (Open-Meteo, Akkudoktor)
│   │   ├── evcc_interface.py      # EV charging control (EVCC integration)
│   │   ├── mqtt_interface.py      # MQTT publish/subscribe + HA auto-discovery
│   │   ├── inverter_fronius.py    # Fronius GEN24 API v1 (legacy)
│   │   ├── inverter_fronius_v2.py # Fronius GEN24 API v2 (firmware-based)
│   │   ├── port_interface.py      # Web server port allocation utility
│   │   ├── optimization_interface.py # Backend abstraction layer
│   │   ├── optimization_backends/  # Backend implementations
│   │   │   ├── optimization_backend_eos.py
│   │   │   └── optimization_backend_evopt.py
│   │   └── config/                # Device-specific config storage
│   │       └── inverter.settings   # Fronius firmware settings
│   ├── web/                       # Frontend assets
│   │   ├── index.html             # Modern dashboard UI
│   │   ├── index_legacy.html      # Legacy dashboard (deprecated)
│   │   ├── js/                    # Client-side JavaScript modules
│   │   │   ├── main.js            # App initialization + coordination
│   │   │   ├── data.js            # API communication and error handling
│   │   │   ├── controls.js        # Control UI and override logic
│   │   │   ├── battery.js         # Battery visualization + SOC limits
│   │   │   ├── chart.js           # Time-series charting (optimization data)
│   │   │   ├── evcc.js            # EV charging status
│   │   │   ├── logging.js         # Log viewer with filtering
│   │   │   ├── ui.js              # UI state management
│   │   │   ├── schedule.js        # Schedule visualization
│   │   │   ├── statistics.js      # Performance stats
│   │   │   ├── bugreport.js       # Bug reporting helper
│   │   │   └── constants.js       # Frontend constants
│   │   └── css/                   # Stylesheets
│   └── json/                      # Runtime data files
│       ├── optimize_request.json   # Last optimization request (written by main loop)
│       ├── optimize_response.json  # Last optimization response (written by main loop)
│       └── test/                  # Test data files
│           ├── *.test.json        # Test fixtures for local UI testing
├── tests/                         # Test suite
│   ├── test_control_states.py     # Control mode state machine tests
│   └── interfaces/                # Per-interface test modules
├── docs/                          # Documentation
├── config.yaml                    # User configuration (created on first run)
├── Dockerfile                     # Container build
├── docker-compose.yml             # Local dev environment
├── requirements.txt               # Python dependencies
├── README.md                      # Project overview
└── .planning/                     # GSD planning documents
    └── codebase/                  # Architecture analysis
```

## Directory Purposes

**`src/`**
- Purpose: Core application code (Python)
- Contains: Entry point, interfaces, configuration management, logging
- Key pattern: Interface-based plugin architecture for extensibility

**`src/interfaces/`**
- Purpose: Pluggable adapters for external systems
- Contains: Data source drivers (load, price, PV), hardware drivers (inverter, battery, EVCC), coordination logic (base_control)
- Naming pattern: `{system}_interface.py` or `{system}_{variant}.py`
- Entry point: All instantiated in `eos_ha.py` lines 336-368 after config loads

**`src/interfaces/optimization_backends/`**
- Purpose: Implementation of different optimization engines
- Contains: EOS Server API adapter, EVopt API adapter
- Selection: Determined by config.yaml `eos.source` field at runtime
- Pattern: Backend abstraction allows new optimizers to be added without changing core

**`src/web/`**
- Purpose: Dashboard UI and REST API endpoints
- Entry points:
  - HTML: `index.html` served by Flask route `/` (line 1353)
  - API: JSON endpoints handled by Flask routes (lines 1423-1860)
- Static files: JS modules and CSS served dynamically (lines 1365-1420)
- API design: RESTful GET/POST for controls, logs, optimization data

**`tests/`**
- Purpose: Test suite
- Key file: `test_control_states.py` - tests BaseControl state machine (7 modes, transitions, overrides)
- Interface tests: One test module per interface (in `tests/interfaces/` subdirectory)
- Test data: JSON fixtures in `src/json/test/` for UI testing

**`.planning/codebase/`**
- Purpose: GSD analysis documents (generated by orchestrator)
- Contains: ARCHITECTURE.md, STRUCTURE.md, CONVENTIONS.md, TESTING.md, STACK.md, INTEGRATIONS.md, CONCERNS.md

## Key File Locations

**Entry Points:**
- `src/eos_ha.py` (lines 1862-1926): Application startup; initializes all interfaces, starts scheduler, web server
- `src/web/js/main.js`: Frontend initialization; sets up data polling and UI rendering

**Configuration:**
- `src/config.py`: ConfigManager class; loads config.yaml with defaults
- `config.yaml`: User-editable YAML; defines all system parameters (created on first run)

**Core Logic:**
- `src/eos_ha.py` (lines 384-619): create_optimize_request() - aggregates 48h forecast data
- `src/eos_ha.py` (lines 849-940): OptimizationScheduler.__run_optimization_loop() - main cycle
- `src/interfaces/base_control.py`: BaseControl class - state machine and control logic
- `src/interfaces/optimization_interface.py`: Backend abstraction and response parsing

**Testing:**
- `tests/test_control_states.py`: Control mode tests (7 modes, transitions, duration tracking)
- `tests/interfaces/`: Per-interface unit tests

**Optimization Data:**
- `src/json/optimize_request.json`: Last request sent to optimizer (written at line 881-884)
- `src/json/optimize_response.json`: Last response received (written at line 922-925)
- API endpoints: `/json/optimize_request.json`, `/json/optimize_response.json` (lines 1423-1442)

## Naming Conventions

**Files:**
- `{system}_interface.py`: Adapter for external system (load_interface.py, battery_interface.py)
- `{device}_{version}.py`: Device-specific with version (inverter_fronius.py, inverter_fronius_v2.py)
- `optimization_backend_{engine}.py`: Backend implementation (optimization_backend_eos.py)
- `{feature}.js`: Frontend module (controls.js, battery.js, chart.js)

**Functions/Methods:**
- `get_*()`: Retrieve state or data (get_current_soc(), get_optimize_request())
- `set_*()`: Update state or config (set_mode_override(), set_min_soc())
- `fetch_*()`: Call external API (fetch_soc_data_from_openhab())
- `update_*()`: Refresh cached data (update_publish_topics(), update_prices())
- `optimize()`: Main interface method (in OptimizationInterface)
- `__private_method()`: Double underscore for true private methods (Python convention)

**Variables:**
- `current_*`: Runtime state (current_ac_charge_demand, current_overall_state)
- `last_*`: Previous value (last_ac_charge_demand, last_response_timestamp)
- `time_frame_base`: Global time resolution (3600 for hourly, 900 for 15-min)
- `config`: Loaded configuration dictionary (always config_manager.config)
- Abbreviations: `soc` (State of Charge), `dyn` (dynamic), `max` (maximum), `w` (watts), `wh` (watt-hours)

**Classes/Types:**
- Interface classes use PascalCase (BaseControl, LoadInterface, BatteryInterface)
- Private attributes: `_single_underscore` for protected, `__double_underscore` for private

## Where to Add New Code

**New Optimization Backend:**
- File: `src/interfaces/optimization_backends/optimization_backend_{name}.py`
- Template: Inherit from or mimic EOSBackend/EVOptBackend structure
- Interface: Must implement optimize(eos_request, timeout) → tuple(response_dict, avg_runtime)
- Output format: Must return valid EOS response (ac_charge, dc_charge, discharge_allowed arrays)
- Register: Add case in OptimizationInterface.__init__() (line 42-55) to instantiate

**New Data Source Interface:**
- File: `src/interfaces/{source}_interface.py`
- Template: Follow LoadInterface or PriceInterface pattern
- Config: Add to config.yaml defaults (src/config.py around line 36+)
- Instantiation: Add initialization in eos_ha.py after line 368
- Integration: Connect via callback or getter method in main loop

**New Device/Inverter Support:**
- File: `src/interfaces/inverter_{brand}.py` or `src/interfaces/{device}_interface.py`
- Methods: implement set_mode_force_charge(), set_mode_avoid_discharge(), set_mode_allow_discharge()
- Selection: Add case in eos_ha.py lines 143-194 (inverter type checking)
- Config: Extend inverter config section in config.py (line ~125)

**New Control Mode (beyond 7 existing):**
- Edit: `src/interfaces/base_control.py` lines 15-33 (MODE constants and state_mapping)
- Implementation: Add case in change_control_state() (eos_ha.py lines 1240-1315)
- Testing: Add test case in tests/test_control_states.py

**New Web Dashboard Feature:**
- Frontend module: `src/web/js/{feature}.js`
- Main coordination: Add to src/web/js/main.js initialization
- Styling: Add to `src/web/css/` (create new file if needed)
- API endpoint: Add Flask route in eos_ha.py (after line 1860)
- HTML: Add DOM elements/section to src/web/index.html

**Tests:**
- File: `tests/test_{feature}.py` or `tests/interfaces/test_{interface_name}.py`
- Run: python -m pytest tests/
- Coverage: Aim for critical path (interface methods, state transitions, error cases)

## Special Directories

**`src/json/`**
- Purpose: Runtime output from optimization loop
- Generated: Yes (written by __run_optimization_loop() in OptimizationScheduler)
- Committed: No (contains transient data; .gitignore excludes *.json)
- Use: Web dashboard reads these files to display last request/response

**`src/json/test/`**
- Purpose: Test data for local UI testing (without real optimizer)
- Generated: No (manually created test fixtures)
- Committed: Yes (helps with development/debugging)
- Pattern: Named as `{data}.test.json`; served via `/json/test/{filename}` endpoint (line 1550)

**`src/interfaces/config/`**
- Purpose: Persistent device configuration (not user-facing)
- Generated: Yes (created by Fronius interface when firmware settings are cached)
- Committed: No (device-specific, varies per installation)
- Contains: inverter.settings (Fronius firmware info)

**`src/web/css/`**
- Purpose: Stylesheets for dashboard
- Generated: No (static assets)
- Committed: Yes

**.planning/codebase/**
- Purpose: Auto-generated architecture analysis documents
- Generated: Yes (by GSD orchestrator)
- Committed: Yes (useful for reference)
- Use: Referenced by /gsd:plan-phase and /gsd:execute-phase commands

---

*Structure analysis: 2026-02-14*
