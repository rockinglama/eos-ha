# External Integrations

**Analysis Date:** 2026-02-14

## APIs & External Services

**Electricity Price APIs:**
- Akkudoktor - Default price source
  - Endpoint: `https://api.akkudoktor.net/prices`
  - SDK/Client: requests library
  - Auth: None (public API)
  - Config: `config.price.source = "akkudoktor"` (default)
  - Used in: `src/interfaces/price_interface.py` (PriceInterface class)

- Tibber API - Hourly electricity price data
  - Endpoint: `https://api.tibber.com/v1-beta/gql`
  - SDK/Client: requests library (GraphQL queries)
  - Auth: Bearer token
  - Config env var: `token` in `config.price`
  - Used in: `src/interfaces/price_interface.py`

- SmartEnergy AT - Austrian electricity prices
  - Endpoint: `https://apis.smartenergy.at/market/v1/price`
  - SDK/Client: requests library
  - Auth: None
  - Config: `config.price.source = "smartenergy_at"`
  - Used in: `src/interfaces/price_interface.py`

- Stromligning.dk - Danish electricity prices
  - Endpoint: `https://stromligning.dk/api/prices?lean=true`
  - SDK/Client: requests library
  - Auth: Bearer token (supplier/product/group)
  - Config env var: `token` in `config.price`
  - Used in: `src/interfaces/price_interface.py`

**Solar PV Forecast APIs:**
- Akkudoktor PV Forecast - Default forecast source
  - Endpoint: `https://api.akkudoktor.net/forecast`
  - SDK/Client: requests library (+ aiohttp for async)
  - Auth: Optional API key (if configured)
  - Config: `config.pv_forecast_source.source = "akkudoktor"` (default)
  - Used in: `src/interfaces/pv_interface.py` (PvInterface class)

- Open-Meteo Solar Forecast - Free solar forecast
  - SDK/Client: open-meteo-solar-forecast library (wrapper)
  - HTTP: aiohttp (async requests)
  - Auth: None (public API)
  - Config: `config.pv_forecast_source.source = "openmeteo"`
  - Used in: `src/interfaces/pv_interface.py`

- Forecast.Solar - Alternative solar forecast
  - SDK/Client: requests library
  - Auth: Optional API key
  - Config: `config.pv_forecast_source.source = "forecast_solar"`
  - Used in: `src/interfaces/pv_interface.py`

- Solcast - Commercial solar forecast
  - Endpoint: API endpoint via package
  - SDK/Client: requests library
  - Auth: Required - API key
  - Config env var: `api_key` in `config.pv_forecast_source`, `resource_id` (optional)
  - Used in: `src/interfaces/pv_interface.py`

**Optimization Engines:**
- EOS Optimization Server
  - Endpoint: Configurable (default via `config.eos.server`)
  - SDK/Client: requests library (POST requests)
  - Auth: None (internal network assumed)
  - Config: `config.eos.source = "eos_server"`, `config.eos.server = "192.168.100.100"`
  - Used in: `src/interfaces/optimization_backends/optimization_backend_eos.py` (EOSBackend class)
  - Protocol: REST API with EOS-format JSON payload

- EVopt Optimization Server
  - Endpoint: Configurable (via `config.eos.server`)
  - SDK/Client: requests library (POST to `/optimize/charge-schedule`)
  - Auth: None
  - Config: `config.eos.source = "evopt"`
  - Used in: `src/interfaces/optimization_backends/optimization_backend_evopt.py` (EVOptBackend class)
  - Protocol: REST API - accepts EOS format, transforms to/from EVopt format

**Inverter Integration:**
- Fronius GEN24 Web API (REST)
  - Endpoint: `http://<inverter-address>/api/` (configurable)
  - SDK/Client: requests library
  - Auth: Digest authentication with MD5 hashing
  - Config: `config.inverter.address`, `config.inverter.user`, `config.inverter.password`
  - Used in: `src/interfaces/inverter_fronius.py` (FroniusWR class) and `src/interfaces/inverter_fronius_v2.py` (FroniusWRV2 class)
  - Features: Battery charge rate control, power readings, configuration management
  - Quirk: Requires nonce-based digest auth on each request

**Smart Meter/Load Data Sources:**
- OpenHAB REST API
  - Endpoint: `http://openhab:8080/rest/`
  - SDK/Client: requests library
  - Auth: None (local network)
  - Config: `config.load.source = "openhab"`, `config.load.url = "http://openhab:8080"`
  - Used in: `src/interfaces/load_interface.py` (LoadInterface class) and `src/interfaces/battery_interface.py`
  - Sensors: load_sensor, car_charge_load_sensor, additional_load_1_sensor, soc_sensor

- Home Assistant REST API
  - Endpoint: `http://homeassistant:8123/api/`
  - SDK/Client: requests library
  - Auth: Bearer token (access_token)
  - Config: `config.load.source = "homeassistant"`, `config.load.url = "http://homeassistant:8123"`, `config.load.access_token`
  - Used in: `src/interfaces/load_interface.py` and `src/interfaces/battery_interface.py`
  - Request timeout: Configurable (default 10s, env var `config.request_timeout`)
  - Sensors: load_sensor, car_charge_load_sensor, additional_load_1_sensor, soc_sensor

**EV Charging Control:**
- EVCC (Electric Vehicle Charging Controller) API
  - Endpoint: `http://yourEVCCserver:7070` (configurable)
  - SDK/Client: requests library
  - Auth: None
  - Config: `config.evcc.url` (default: `http://yourEVCCserver:7070`)
  - Used in: `src/interfaces/evcc_interface.py` (EvccInterface class)
  - Endpoints:
    - `GET /api/state` - Fetch charging state and mode
    - `POST /api/chargeModes/{mode}` - Set charging mode
    - `POST /api/chargeLimits/{soc}` - Set charge limit
    - `POST /api/maxCurrents/{current}` - Set max current
  - Features: Charging mode control, SOC/current management, mode change callbacks

## Data Storage

**Databases:**
- None detected - Uses in-memory state and configuration files

**File Storage:**
- Local filesystem only
  - Config: `src/config.yaml` (YAML format)
  - Logs: In-memory buffer + console output (via MemoryLogHandler in `src/log_handler.py`)
  - Debug JSON: `src/json/optimize_request.json`, `src/json/optimize_response.json`

**Caching:**
- In-memory via Python objects (no external cache service)
- Background update threads with configurable intervals

## Authentication & Identity

**Auth Provider:**
- Custom implementations per integration
- Types:
  - Bearer tokens (Home Assistant, Tibber, Stromligning)
  - Digest authentication (Fronius inverters)
  - API keys (Solcast)
  - None (Local network APIs)

**Implementation:**
- Tokens stored in config.yaml (environment-specific)
- No centralized auth system; each interface handles its own credentials
- TLS support for MQTT (optional, via config)

## Monitoring & Observability

**Error Tracking:**
- None detected (no Sentry, Rollbar, etc.)

**Logs:**
- Approach: Python logging module with custom MemoryLogHandler
- Location: `src/log_handler.py` (MemoryLogHandler class)
- Level: Configurable via `config.log_level` (DEBUG, INFO, WARNING, ERROR)
- Output: Console (stdout) and in-memory circular buffer
- Timezone: Configured via `config.time_zone` with custom TimezoneFormatter
- Web endpoint: `GET /logs` and `GET /logs/alerts` (JSON format)
- Features: Alert detection, stats collection, log clearing

## CI/CD & Deployment

**Hosting:**
- Containerized (Docker)
- Docker image: `python:3.13-slim`
- Registry: `ghcr.io/ohand/eos_connect:snapshot`

**CI Pipeline:**
- GitHub Actions (present in `.github/` directory)
- Auto-versioning via git tags (recent commits show version bumps)

## Environment Configuration

**Required env vars:**
None in Docker (all via config.yaml). For API integrations, required in config.yaml:
- Electricity price: `config.price.token` (for Tibber/Stromligning)
- Solar forecast: `config.pv_forecast_source.api_key` (for Solcast, optional for others)
- Home Assistant: `config.load.access_token`, `config.battery.access_token`
- Fronius inverter: `config.inverter.user`, `config.inverter.password`
- MQTT: `config.mqtt.user`, `config.mqtt.password` (optional)
- EOS/EVopt: `config.eos.server`

**Secrets location:**
- Config file: `src/config.yaml` (mounted at `/app/config.yaml` in Docker via `docker-compose.yml`)
- No .env file detected; Docker environment variables passed via compose

## Webhooks & Callbacks

**Incoming:**
- None detected (polling-based only)

**Outgoing:**
- None detected (read-only integrations, one-way control)

**State-based Callbacks:**
- MQTT publish (outgoing): eos_connect publishes state to MQTT broker
  - Via `src/interfaces/mqtt_interface.py` (MqttInterface.publish_message())
  - Topics: Home Assistant auto-discovery topics, state topics
  - Used for: Home Assistant integration, dashboard updates

- EVCC mode/state change callbacks:
  - EvccInterface detects charging state/mode changes and triggers callback
  - Used in: `src/eos_connect.py` main loop to react to EV charging events

- Optimization result callbacks:
  - Optimization backends return scheduling data for control commands
  - No webhook; processed synchronously in main event loop

## Request Retry & Timeout Strategy

**Retry Configuration:**
- LoadInterface: Max retries + exponential backoff
  - `max_retries` config (default 5)
  - `retry_backoff` config (default 1 second, exponential)
  - `warning_threshold` config (escalation point)
  - Used in: `src/interfaces/load_interface.py`

**Timeout:**
- Global request timeout: `config.request_timeout` (default 10 seconds, range 5-120)
- Specific overrides: Individual API clients may set their own timeouts
- Applied to: Home Assistant, OpenHAB API calls

## Rate Limiting

**Not detected** - No explicit rate limiting implemented. Relies on:
- Background update intervals (configurable per interface)
- Natural API throttling by external services

---

*Integration audit: 2026-02-14*
