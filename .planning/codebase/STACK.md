# Technology Stack

**Analysis Date:** 2026-02-14

## Languages

**Primary:**
- Python 3.13 - Main application runtime (requires 3.11+)

## Runtime

**Environment:**
- Python 3.13 (Docker: `python:3.13-slim`)

**Package Manager:**
- pip - Python package manager
- Lockfile: `requirements.txt` present

## Frameworks

**Core:**
- Flask 2.2.5+ - Web framework for REST API and web interface (`src/eos_connect.py`)

**Async/Networking:**
- gevent 24.2.1+ - Lightweight concurrency via WSGI server (`src/interfaces/port_interface.py`)
- aiohttp - Async HTTP client for PV forecasts (`src/interfaces/pv_interface.py`)
- requests 2.26.0+ - HTTP client for API integrations (multiple interfaces)
- paho-mqtt 2.1.0+ - MQTT protocol client (`src/interfaces/mqtt_interface.py`)

**Data Processing:**
- pandas 2.2.3+ - Time series and data aggregation
- numpy 2.0.0+ - Numerical computations
- open-meteo-solar-forecast 0.1.22+ - Solar forecast library (`src/interfaces/pv_interface.py`)

**Configuration & Utilities:**
- pyyaml 6.0+ - YAML config parsing (`src/config.py`)
- ruamel.yaml 0.18.17 - Advanced YAML with comments (`src/config.py`)
- pytz 2025.1+ - Timezone handling
- packaging 23.2+ - Version comparison and parsing

**System:**
- psutil 7.0.0+ - Process and system utilities (`src/interfaces/port_interface.py`)

## Key Dependencies

**Critical:**
- Flask - HTTP server for REST API endpoints and web UI
- requests - HTTP client for all external API calls (Tibber, Akkudoktor, EVopt, EOS, Fronius, etc.)
- paho-mqtt - MQTT broker communication for Home Assistant integration

**Infrastructure:**
- gevent - WSGI server implementation (non-blocking I/O)
- pandas/numpy - Energy data processing and optimization math

**External APIs:**
- aiohttp - Async HTTP for PV forecast APIs
- open-meteo-solar-forecast - Open Meteo API wrapper

## Configuration

**Environment:**
- Configuration via `config.yaml` (mounted at `/app/config.yaml` in Docker)
- Environment variable: `PYTHONUNBUFFERED=1` (Docker, for log streaming)
- Reads config from: `src/config.py` (ConfigManager class)

**Build:**
- Dockerfile: Multi-stage build using `python:3.13-slim`
- docker-compose.yml: Container orchestration with volume mount for config
- Entry point: `CMD ["python", "eos_connect.py"]`

## Web Server

**Port:** 8081 (configurable via port selection logic in `src/interfaces/port_interface.py`)

**Server Type:**
- WSGI server using gevent.pywsgi.WSGIServer
- Automatic port fallback if 8081 unavailable

**Endpoints:**
- `GET /` - Main UI (Flask routes: `src/eos_connect.py`)
- `GET /index_legacy.html` - Legacy interface
- `GET /logs` - Application logs
- `GET /logs/alerts` - Alert logs
- `POST /logs/clear` - Clear logs
- `POST /controls/mode_override` - Control override
- `GET /json/optimize_request.json` - Optimization request state
- `GET /json/optimize_response.json` - Optimization response state
- `GET /json/current_controls.json` - Current control state
- Static files: `/css/<filename>`, `/js/<filename>`

## Platform Requirements

**Development:**
- Python 3.11 or higher
- pip for dependency installation

**Production:**
- Docker 20.10+
- docker-compose 1.29+ (optional, for container orchestration)
- Target platform: Linux containers (deployed on various server types)

---

*Stack analysis: 2026-02-14*
