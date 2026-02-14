# Architecture

**Analysis Date:** 2026-02-14

## Pattern Overview

**Overall:** Multi-layer orchestration system with plugin-based interfaces and centralized control. EOS HA acts as an integration and control hub that coordinates between hardware (inverters, batteries, EVs), data sources (pricing, PV forecasts, consumption), and optimization backends (EOS or EVopt).

**Key Characteristics:**
- **Orchestration-driven**: Periodic optimization loop (configurable interval) fetches data → sends to optimizer → applies control decisions
- **Interface-based abstraction**: Each data source/device has a pluggable interface (LoadInterface, BatteryInterface, PriceInterface, etc.)
- **Multi-threaded scheduling**: Separate background threads for optimization, control state updates, and data fetching
- **Flask-based web dashboard**: Real-time monitoring and manual control via REST API
- **MQTT integration**: Home Assistant/OpenHAB integration via MQTT auto-discovery

## Layers

**Application Layer (Entry Point):**
- **Location**: `src/eos_ha.py`
- **Purpose**: Main orchestration engine; manages initialization, threading, web server, and lifecycle
- **Contains**: Flask app, route handlers, optimization scheduler, callbacks, logging
- **Depends on**: All interfaces, ConfigManager, OptimizationInterface
- **Used by**: Web clients (JavaScript), external systems via REST API

**Configuration Layer:**
- **Purpose**: YAML-based centralized configuration management
- **Location**: `src/config.py`
- **Contains**: ConfigManager class for loading/validating config.yaml with defaults for all subsystems
- **Depends on**: ruamel.yaml
- **Used by**: Main application during initialization

**Optimization Interface Layer:**
- **Location**: `src/interfaces/optimization_interface.py`
- **Purpose**: Abstraction layer for optimization backends (EOS vs EVopt)
- **Contains**: OptimizationInterface class that delegates to backend implementations
- **Depends on**: Backend implementations (EOSBackend, EVOptBackend)
- **Used by**: Main optimization loop in eos_ha.py

**Backend Implementation Layer:**
- **Location**: `src/interfaces/optimization_backends/`
- **Purpose**: Format transformation and API communication with external optimizers
- **Contains**:
  - `optimization_backend_eos.py`: EOS API communication (async, JSON format v0.0.1 or v0.0.2)
  - `optimization_backend_evopt.py`: EVopt API communication (15-min or hourly slots)
- **Depends on**: requests, time utilities
- **Used by**: OptimizationInterface

**Data Source Interfaces Layer:**
- **Purpose**: Pluggable adapters for each external data source
- **Location**: `src/interfaces/`
- **Interfaces**:
  - `load_interface.py`: Fetch consumption from Home Assistant, OpenHAB, or static profile
  - `battery_interface.py`: Get battery SOC, manage dynamic charge limits based on temp/SOC
  - `price_interface.py`: Fetch electricity prices (Tibber, Stromligning, SmartEnergy, Akkudoktor)
  - `pv_interface.py`: Fetch PV forecasts (Open-Meteo API, Akkudoktor API)
  - `evcc_interface.py`: Monitor/control EV charging (EVCC integration)
  - `mqtt_interface.py`: Home Assistant/OpenHAB MQTT publishing and auto-discovery
  - `port_interface.py`: Web server port allocation and health checking

**Device Control Interfaces Layer:**
- **Purpose**: Hardware communication and command execution
- **Interfaces**:
  - `base_control.py`: Core state machine; converts optimization output to inverter commands (7 modes)
  - `inverter_fronius.py`: Legacy Fronius GEN24 API v1
  - `inverter_fronius_v2.py`: Enhanced Fronius GEN24 API v2 (firmware-based auth)
- **Depends on**: requests for HTTP communication
- **Used by**: change_control_state() in main loop

**Logging & Support Layer:**
- **Location**: `src/log_handler.py`
- **Purpose**: In-memory logging with alerts buffer for web dashboard
- **Contains**: MemoryLogHandler class; manages 50k general logs + 2k alert-specific logs

**Web Interface Layer:**
- **Location**: `src/web/`
- **Purpose**: Real-time dashboard, monitoring, and manual control
- **Contains**:
  - `index.html`: Modern dashboard UI
  - `js/main.js`: App initialization and coordination
  - `js/data.js`: API data fetching and error handling
  - `js/controls.js`: Control UI and override logic
  - `js/battery.js`: Battery visualization and limits
  - `js/chart.js`: Time-series charting
  - `js/evcc.js`: EV charging status display
  - `js/logging.js`: Log viewer and alert filtering
  - `js/ui.js`: UI state management
- **API endpoints** (all in eos_ha.py):
  - `GET /`: Main page
  - `GET /json/current_controls.json`: Current system state
  - `GET /json/optimize_request.json`: Last optimization input
  - `GET /json/optimize_response.json`: Last optimization output
  - `POST /controls/mode_override`: Manual mode override
  - `GET /logs`, `/logs/alerts`, `/logs/stats`: Log retrieval

## Data Flow

**Optimization Cycle (Periodic):**

1. **Data Collection** (~13 seconds startup, then ~1-5 min intervals)
   - LoadInterface fetches consumption data (Home Assistant/OpenHAB/static)
   - BatteryInterface fetches current SOC and calculates dynamic max charge
   - PriceInterface fetches hourly/15-min electricity prices
   - PvInterface fetches 48-hour PV forecasts
   - All data is time-aligned to 48-hour window

2. **Request Creation** (create_optimize_request() in eos_ha.py)
   - Aggregates all forecast data into EOS format:
     - `pv_prognose_wh`: PV generation forecast array
     - `strompreis_euro_pro_wh`: Grid import prices
     - `einspeiseverguetung_euro_pro_wh`: Feed-in prices
     - `preis_euro_pro_wh_akku`: Battery charging cost
     - `gesamtlast`: Total consumption forecast
   - Includes device parameters (battery capacity, inverter rates, etc.)
   - Detects DST changes and adjusts timestamps

3. **Optimization** (OptimizationInterface.optimize())
   - Sends request to EOS Server or EVopt (configurable)
   - Returns control strategy for next 48 hours with per-hour/15-min decisions:
     - AC charge demand (grid charging rate, 0-1 relative)
     - DC charge demand (PV charging rate, 0-1 relative)
     - Discharge allowed (boolean)

4. **Control Extraction** (examine_response_to_control_data())
   - Parses response; extracts current hour's control values
   - Stores next hour's control for fast control loop
   - Validates against safety limits (e.g., don't exceed max SOC)

5. **State Application** (setting_control_data() + change_control_state())
   - BaseControl applies relative demands to absolute power (using max_charge_power_w)
   - Applies overrides (manual mode, EVCC charging state, battery SOC limits)
   - Selects inverter mode: 0=Grid Charge, 1=Avoid Discharge, 2=Allow Discharge, 3-6=EVCC variants
   - Sends commands to inverter (Fronius API or EVCC external battery mode)
   - Publishes updated state to MQTT

**Fast Control Loop (Every 1 second):**
- Monitors hour boundary; if hour changes, applies control for new hour without waiting for next optimization
- Allows rapid response to optimizer decisions at hour transitions

**Data Loop (Every 15 seconds):**
- Fetches Fronius inverter temperatures and fan speeds
- Updates MQTT topics for visibility

**State Management:**
- **Optimization Scheduler** manages three background threads:
  - Optimization loop: Executes every N minutes (configurable refresh_time), sleeps intelligently based on average runtime
  - Control loop: Applies hourly control decisions at 1-second granularity
  - Data loop: Updates inverter metrics every 15 seconds
- **BaseControl** holds runtime state:
  - Current AC/DC charge demands (relative 0-1)
  - Current discharge_allowed status
  - Overall mode (0-6)
  - Override active flag + end time
  - Battery SOC and EVCC charging state

## Key Abstractions

**Interface Pattern (Plugin Architecture):**
- **Purpose**: Each external system (inverter, data source) is abstracted behind a named interface
- **Implementation**:
  - LoadInterface: Multiple source backends (openhab, homeassistant, default)
  - PriceInterface: Multiple price APIs (tibber, akkudoktor, stromligning, fixed_24h)
  - PvInterface: Multiple forecast sources (open-meteo, akkudoktor)
  - Device interfaces: Fronius V1/V2, EVCC, etc.
- **Pattern**: Abstract parent + config-driven instantiation in eos_ha.py
- **Benefit**: Add new data source by writing new adapter, no core logic changes

**Optimization Backend Abstraction:**
- OptimizationInterface accepts EOS-format requests
- Backend implementations (EOS, EVopt) handle format mapping and API calls
- Allows swapping optimization engine without changing main orchestration

**Control State Machine (BaseControl):**
- Encapsulates all state: demands, SOC, EVCC status, overrides
- Provides getter methods for safe read access to state
- Implements mode transition logic and duration tracking
- Allows manual override with expiry time

**Configuration-Driven Initialization:**
- All interfaces instantiated from config.yaml in main
- No hardcoded service endpoints; all configurable
- Default values for all optional settings

## Entry Points

**Application Entry:**
- **Location**: `src/eos_ha.py` (lines 1862-1926)
- **Triggers**: `python src/eos_ha.py [config_dir]`
- **Responsibilities**:
  - Load config and validate Python version
  - Initialize all interfaces (load, battery, price, pv, inverter, mqtt, evcc)
  - Start OptimizationScheduler (3 background threads)
  - Start Flask web server
  - Register callbacks for state changes (EVCC, battery, MQTT)
  - Graceful shutdown on Ctrl+C

**Web API Entry:**
- **Location**: `src/eos_ha.py` (routes starting line 1338)
- **Endpoints**:
  - `GET /`: Main dashboard (renders index.html)
  - `GET /json/current_controls.json`: System state (all current values)
  - `POST /controls/mode_override`: Accept manual override
  - `GET /logs*`: Log endpoints for alerts, filtering, stats
- **Authentication**: None (designed for trusted network or behind proxy)

**Background Scheduler Entry:**
- **Location**: OptimizationScheduler in eos_ha.py (lines 693-1144)
- **Triggers**: Auto-started on app init
- **Responsibilities**:
  - Runs optimization every N minutes (smart sleep based on runtime)
  - Applies control every hour transition
  - Updates inverter data every 15 seconds

## Error Handling

**Strategy:** Defensive with fallback defaults

**Patterns:**

**Network Errors** (requests.exceptions):
- Retry with exponential backoff (LoadInterface, PriceInterface)
- Log as WARNING after threshold; escalate to ERROR only on max retries
- Fall back to cached/default values (prices default to 10ct/kWh; consumption from profile)
- Never block optimization loop; log and continue

**Configuration Errors**:
- Validate at load time (ConfigManager.load_config())
- Create example config if missing
- Log missing required fields but attempt to use sensible defaults
- Safety check: max_soc > min_soc, capacity_wh > 0 validated in BatteryInterface

**API Response Errors**:
- Optimization backends: Catch JSON parse errors, validate response structure
- Check for error flags in response; if present, don't apply control (safety)
- Log full request/response to `src/json/optimize_request.json` and `optimize_response.json` for debugging

**Safety Overrides** (in setting_control_data()):
- Prevent AC charging if battery SOC >= max_soc (even if optimizer requests it)
- Cap charge power to min of: (optimizer demand, dynamic max based on SOC/temp, configured max)
- Validate EVCC charging state before applying

## Cross-Cutting Concerns

**Logging:**
- Tool: Python logging module with MemoryLogHandler
- Strategy: All modules log to `__main__` logger with `[COMPONENT]` prefix
- In-memory buffer: 50k general logs + 2k alerts (WARNING/ERROR/CRITICAL)
- Web API: `/logs` endpoint provides filtered access (by level, timestamp, limit)

**Validation:**
- **Configuration**: ConfigManager validates YAML schema at startup
- **Optimization Request**: create_optimize_request() ensures 48-hour arrays align
- **Optimization Response**: examine_response_to_control_data() validates values are numeric
- **Control Limits**: BaseControl and inverter classes cap values to safe ranges

**Authentication:**
- **MQTT**: Username/password from config (optional TLS)
- **Data Sources**: API tokens from config (Home Assistant, Tibber, etc.)
- **Web API**: No authentication (assumes private network)
- **Inverter**: Username/password from config (Fronius)

**Timezone Handling**:
- Configured via config.yaml (`time_zone` field)
- All internal timestamps use configured timezone (pytz)
- Web dashboard converts to user's browser timezone for display
- Price/PV data: Aligned to optimization time frame (hourly/15-min slots)

---

*Architecture analysis: 2026-02-14*
