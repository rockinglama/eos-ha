# Phase 1: Foundation & Data Flow - Context

**Gathered:** 2026-02-14
**Status:** Ready for planning

<domain>
## Phase Boundary

Integration appears in HA UI, connects to EOS server, runs periodic optimization cycle, and processes data flow end-to-end. Users can install via HACS, configure via Config Flow (EOS URL, entity selection, battery parameters), and the integration collects data from HA entities + Akkudoktor API, sends optimization requests to EOS, and processes responses. Output entities and runtime configuration belong to later phases.

</domain>

<decisions>
## Implementation Decisions

### Config Flow structure
- **3-step Config Flow:**
  - Step 1: EOS server URL + validation (reachable, correct response)
  - Step 2: Entity selection (price, SOC, consumption) — all three required
  - Step 3: Battery parameters (capacity, max charge power, min/max SOC, inverter power)
- Location (lat/lon) pulled from Home Assistant's home zone — not user-entered
- Entity selector shows all entities but suggests/highlights matching device classes
- Pre-filled sensible defaults for battery parameters (user can adjust)
- Battery capacity unit: kWh (not Wh)

### Missing data behavior
- If any HA input entity is unavailable: skip optimization, keep last valid results, try again next cycle
- PV forecast (Akkudoktor API): cache last successful forecast, use cached data if API is down (cache valid for 6 hours)
- If cached PV forecast is older than 6 hours and API is still down: skip optimization
- Optimization status entity: expose whether last run was successful + timestamp — user can check at a glance if data is fresh

### EOS server connection
- URL only, no authentication
- Supports both HTTP and HTTPS URLs
- Config Flow Step 1 validates server is reachable AND returns expected response — rejects setup if response is unexpected
- After setup: server failures shown via optimization status entity only (no persistent notifications, no log spam)
- Claude to check EOS source/docs for correct API endpoint and request/response format

### Claude's Discretion
- Exact Config Flow field labels and descriptions
- Default battery parameter values
- Optimization status entity format and attributes
- DataUpdateCoordinator polling implementation
- Error retry timing and backoff strategy
- Logging verbosity levels

</decisions>

<specifics>
## Specific Ideas

- User wants battery capacity in kWh, not Wh — familiar unit for battery owners
- Status entity for optimization cycle health — user wants to know at a glance if things are working without checking logs
- Cached PV forecast approach — forecasts don't change rapidly, so a 6-hour window prevents unnecessary optimization skips during brief API outages

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope

</deferred>

---

*Phase: 01-foundation-data-flow*
*Context gathered: 2026-02-14*
