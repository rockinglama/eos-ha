# Codebase Concerns

**Analysis Date:** 2026-02-14

## Tech Debt

**Bare Exception Handler:**
- Issue: Bare `except:` clause masks all errors including system exits and keyboard interrupts
- Files: `src/interfaces/inverter_fronius.py:476`
- Impact: Silent failures when JSON parsing fails; errors not properly logged or handled
- Fix approach: Replace with specific exception type (`except (json.JSONDecodeError, ValueError)`) and log the actual error context

**Overly Silent Exception Handling in Log Handler:**
- Issue: Multiple `pass` statements in exception handlers suppress errors without logging
- Files: `src/log_handler.py:110`, `src/log_handler.py:146`, `src/log_handler.py:151`, `src/log_handler.py:193`, `src/log_handler.py:200`, `src/log_handler.py:221`, `src/log_handler.py:237`, `src/log_handler.py:285`
- Impact: Log handler failures go unnoticed; difficult to debug logging issues in production
- Fix approach: Replace silent `pass` with at least debug-level logging or stderr writes to track exceptions

**Logic Error in Duration Validation:**
- Issue: Validation uses AND instead of OR: `if duration <= 0 and duration <= 12 * 60` always false when duration is valid
- Files: `src/eos_ha.py:1647`
- Impact: Duration validation never rejects invalid values; incorrect durations could reach inverter control
- Fix approach: Change to `if duration <= 0 or duration > 12 * 60` to properly validate range

**Inconsistent Request Timeout Values:**
- Issue: Timeout values vary across HTTP requests (5s, 10s, 15s, 180s) without documented rationale
- Files: `src/interfaces/pv_interface.py:675`, `src/interfaces/pv_interface.py:851`, `src/interfaces/inverter_fronius_v2.py:145`, `src/interfaces/battery_interface.py:217`, `src/interfaces/price_interface.py:523`
- Impact: Some operations may fail unexpectedly due to timeout; no consistency policy
- Fix approach: Define request timeout strategy in constants; use configurable defaults per endpoint type

**Workaround Without Explanation:**
- Issue: PV forecast data processing includes undocumented workaround that removes first entry and appends 0
- Files: `src/interfaces/pv_interface.py:717-719` (comment: "workaround for wrong time points in the forecast from akkudoktor")
- Impact: Data manipulation without clear reasoning; fragile to API changes
- Fix approach: Document why akkudoktor returns misaligned timestamps and formalize the correction logic

## Known Bugs

**Quarter-Hour Alignment Bug (Fixed):**
- Symptoms: Optimization scheduling would schedule tasks in the past under certain conditions
- Files: `src/interfaces/optimization_interface.py:320-328`
- Trigger: When calculated quarter-hour start time falls before current time
- Current Status: Bug fix in place with explicit check and next-quarter fallback
- Note: This fix should be tested to ensure edge cases around quarter boundaries are handled

## Security Considerations

**Hardcoded Credential Values in Default Config:**
- Risk: Default configuration file contains placeholder credentials that could leak if committed or exposed
- Files: `src/config.py:46` (access_token: "abc123"), `src/config.py:72` (password: "your_password")
- Current mitigation: File is created locally, not typically committed; config.yaml is in .gitignore
- Recommendations:
  - Ensure config.yaml is ALWAYS in .gitignore
  - Never output config contents in logs (especially access tokens)
  - Consider requiring explicit setup step for sensitive credentials rather than defaults

**Flask Template Injection Risk:**
- Risk: Using `render_template_string` with file contents could enable SSTI if input is ever user-controlled
- Files: `src/eos_ha.py:1361`, `src/eos_ha.py:1346`
- Current mitigation: Files are read from disk, not user input; proper path handling
- Recommendations:
  - Use `send_file()` instead of `render_template_string()` for static HTML
  - Document why template rendering is necessary if it becomes user-customizable

**File Serving Security:**
- Risk: Dynamic file serving could be exploited with directory traversal
- Files: `src/eos_ha.py:1365-1392` (JS file serving)
- Current mitigation: File extension check (.js only); path existence validation
- Recommendations:
  - Use `send_file()` with restricted directory instead of `send_from_directory()`
  - Validate resolved path is within intended directory using `os.path.realpath()`
  - Log all file serving attempts for audit trail

**No HTTPS Enforcement:**
- Risk: HTTP server communicates sensitive control data (battery charge rates, modes) unencrypted
- Files: `src/eos_ha.py:1334` (Flask app), `src/interfaces/optimization_interface.py:37` (unencrypted server URL)
- Current mitigation: Likely used on local network only
- Recommendations:
  - Document that HTTPS must be configured via reverse proxy in production
  - Add security warning in README for network deployments

## Performance Bottlenecks

**Monolithic Main Module (1925 lines):**
- Problem: Main control logic, web server, scheduling, and data flow management all in one file
- Files: `src/eos_ha.py`
- Cause: Incremental development without refactoring; mixed concerns
- Impact: Difficult to test, maintain, and reason about control flow
- Improvement path:
  - Extract Flask routes to separate `src/web_api.py` module
  - Extract scheduling/optimization loop to `src/scheduler.py`
  - Extract state callbacks to `src/state_manager.py`
  - Keep only main entry point and component initialization

**Large PV Interface Module (1681 lines):**
- Problem: Multiple forecast providers, data aggregation, validation, and background updates in single class
- Files: `src/interfaces/pv_interface.py`
- Cause: Multiple data sources (Akkudoktor, OpenMeteo) merged into one module
- Impact: Complex initialization, difficult to test individual sources
- Improvement path:
  - Extract provider logic to plugin pattern: `pv_providers/akkudoktor.py`, `pv_providers/openmeteo.py`
  - Create base provider interface with common async/retry logic
  - Aggregate results in PvInterface (reduce from ~1600 lines to ~300)

**Battery Price Handler Complexity (1223 lines):**
- Problem: Forensic analysis logic for battery charging cost attribution is data-intensive
- Files: `src/interfaces/battery_price_handler.py`
- Cause: Historical data reconstruction algorithm requires extensive bookkeeping
- Impact: CPU-intensive calculations every 15 minutes; unclear algorithm
- Improvement path:
  - Profile to identify hot paths (likely in charging event identification section)
  - Cache intermediate results for unchanged historical ranges
  - Document algorithm with examples (diagram charging periods, source attribution)

**No Caching Layer for API Responses:**
- Problem: PV forecasts, price data, battery state all fetched on schedule without deduplication
- Files: `src/interfaces/pv_interface.py`, `src/interfaces/price_interface.py`, `src/interfaces/battery_interface.py`
- Cause: Simple polling model; no response caching
- Impact: Redundant API calls if data hasn't changed; unnecessary network overhead
- Improvement path:
  - Implement response hash comparison before state updates
  - Cache forecasts for 5-10 minutes (prevents rapid re-requests)
  - Add optional Redis caching for distributed deployments

## Fragile Areas

**Inverter Authentication State Machine:**
- Files: `src/interfaces/inverter_fronius_v2.py`
- Why fragile: HTTP Digest authentication requires exact nonce handling; multiple firmware versions with different hash algorithms
- Fragility signals:
  - Fallback from SHA256 to MD5 for backward compatibility
  - Algorithm detection from firmware version (lines 59-63)
  - Multiple authentication retry mechanisms
- Safe modification:
  - Test against all supported firmware versions before changes
  - Never modify hash functions without verifying against actual inverters
  - Keep both v1 and v2 implementations active during transitions
- Test coverage: `tests/interfaces/test_inverter_fronius_v2.py` exists but should verify auth edge cases

**Time Zone Handling Across Modules:**
- Files: Spreads across `src/eos_ha.py` (main), `src/interfaces/pv_interface.py` (forecast), `src/interfaces/optimization_interface.py` (scheduling), `src/log_handler.py` (timestamps)
- Why fragile: Timezone conversions at module boundaries; multiple timezone types (pytz, zoneinfo, naive)
- Fragility signals:
  - Mix of pytz and zoneinfo in different modules
  - Timezone passed as parameter to every interface
  - Multiple strftime/fromtimestamp calls per module
- Safe modification:
  - Define timezone once at startup in `src/eos_ha.py`
  - Inject as singleton dependency to all modules needing it
  - Use consistent datetime handling (always timezone-aware, always UTC internally)
- Test coverage: No dedicated timezone tests; edge cases like DST transitions likely untested

**Mode Override Logic:**
- Files: `src/eos_ha.py:1605-1690` (validation and application), `src/interfaces/base_control.py` (state tracking)
- Why fragile: Complex validation with multiple conditions; state management across threads
- Fragility signals:
  - AND/OR logic error in validation (line 1647)
  - No atomic transaction for mode + duration + power updates
  - Override duration parsed from string format ("00:30") without validation
- Safe modification:
  - Add comprehensive unit tests for edge cases (0 duration, negative power, mode -2/-1)
  - Validate all input before any state change
  - Use dataclass or named tuple for override parameters to prevent mismatches
- Test coverage: `tests/test_control_states.py` exists; should test override edge cases

**MQTT Command Handling:**
- Files: `src/interfaces/mqtt_interface.py`
- Why fragile: Unstructured topic-to-callback mapping; no validation schema for commands
- Fragility signals: Manual JSON parsing in callbacks; exception handlers that pass
- Safe modification:
  - Define MQTT command schema (JSON Schema or Pydantic)
  - Centralize validation before callbacks
  - Log all MQTT commands and responses for audit trail
- Test coverage: No MQTT integration tests found

**Optimization Backend Abstraction:**
- Files: `src/interfaces/optimization_interface.py` (abstraction), `src/interfaces/optimization_backends/optimization_backend_eos.py`, `src/interfaces/optimization_backends/optimization_backend_evopt.py` (implementations)
- Why fragile: Different backends return different data structures; conversion logic hidden in backend classes
- Fragility signals:
  - Both backends inherit no common base class
  - Response format conversion not fully documented
  - Error handling differs between backends (one writes debug files, etc.)
- Safe modification:
  - Define formal Backend interface/protocol with required methods
  - Specify response data structure as TypedDict or dataclass
  - Implement consistent error handling across backends
- Test coverage: `tests/interfaces/optimization_backends/` exists; should verify response format consistency

## Scaling Limits

**In-Memory Log Buffer (Fixed Size):**
- Current capacity: 1000 main records, 1000 alerts (configurable in MemoryLogHandler.__init__)
- Limit: After 1000 logs, oldest entries are discarded; long-running applications lose history
- Impact: Cannot investigate issues that occurred hours ago; no persistent log archive
- Scaling path:
  - Add optional file-based log rotation (daily or size-based)
  - Implement log stream upload to central logging service
  - Configure buffer sizes based on deployment target (embed vs. cloud)

**No Database for Historical Data:**
- Current capacity: PV forecasts, prices, battery data stored only in memory/temporary files
- Limit: Multi-day optimization analysis impossible; restart loses all history
- Impact: Cannot correlate optimization decisions with actual outcomes
- Scaling path:
  - Add optional SQLite database for energy statistics
  - Store: hourly energy flows, optimization decisions, actual vs. predicted outcomes
  - Enable retrospective analysis and model improvement

## Dependencies at Risk

**Deprecated ruamel.yaml Version Lock:**
- Risk: `ruamel.yaml==0.18.17` is old (current is 0.19+); fixed version may cause conflicts
- Impact: Security fixes from newer versions not available
- Migration plan:
  - Update to `ruamel.yaml>=0.18.17` (allow newer versions)
  - Test config loading with newer version before release
  - Monitor security advisories for ruamel.yaml

**OpenMeteo Solar Forecast (Low Version Constraint):**
- Risk: `open-meteo-solar-forecast>=0.1.22` is early stage; API may change
- Impact: If package receives major update, async interface or return format could break
- Migration plan:
  - Pin major version: `open-meteo-solar-forecast>=0.1.22,<1.0.0`
  - Implement adapter layer to abstract provider API
  - Test against latest minor versions regularly

**pandas/numpy Version Mismatch Risk:**
- Risk: `pandas>=2.2.3` with `numpy>=2.0.0` may have compatibility edge cases
- Impact: Random runtime errors in numerical operations during edge cases
- Migration plan:
  - Document tested combinations
  - Run CI tests with multiple numpy/pandas versions
  - Use constraints: `numpy>=2.0.0,<3.0.0`, `pandas>=2.2.3,<3.0.0`

## Missing Critical Features

**No Persistent Configuration Versioning:**
- Problem: Config changes are not tracked; can't rollback to previous state
- Blocks: Debugging bad configurations; A/B testing parameter changes
- Solution: Store config history with timestamps; provide rollback API endpoint

**No Comprehensive Error Recovery:**
- Problem: If external API (EOS, EVopt, Tibber, Home Assistant) fails, system degrades gracefully but doesn't auto-recover
- Blocks: High-availability deployments; SLA commitments
- Solution: Implement health checks with automatic reconnection; circuit breaker pattern for failing APIs

**No Observability for Optimization Quality:**
- Problem: Cannot measure if optimization decisions are actually better than naive baseline
- Blocks: Model improvement; validating EVopt vs. EOS backend
- Solution: Log predicted vs. actual energy flow; calculate realized cost savings post-hoc

## Test Coverage Gaps

**Inverter Fronius Integration:**
- What's not tested: Actual HTTP communication; digest authentication with different firmware versions
- Files: `src/interfaces/inverter_fronius.py`, `src/interfaces/inverter_fronius_v2.py`
- Risk: Authentication errors, firmware incompatibilities not caught until production
- Priority: **High** - This is a critical hardware integration point

**PV Forecast Data Handling:**
- What's not tested: Edge cases in forecast aggregation; API error scenarios; timezone transitions
- Files: `src/interfaces/pv_interface.py` (~1681 lines, mostly untested logic)
- Risk: Silent data corruption (negative power values, wrong time alignment); incorrect forecasts affect optimization
- Priority: **High** - Core data source for decision-making

**Timezone and DST Handling:**
- What's not tested: Daylight saving time transitions; cross-timezone operations
- Files: Multiple modules use pytz/zoneinfo
- Risk: Off-by-one errors during DST transitions; scheduling failures
- Priority: **High** - Affects scheduling and timing-critical operations

**Mode Override Edge Cases:**
- What's not tested: All combinations of mode values (-2 to 6) with valid/invalid durations
- Files: `src/eos_ha.py:1605-1690`, `src/interfaces/base_control.py`
- Risk: Validation logic error (line 1647) means invalid overrides accepted
- Priority: **High** - User-facing control feature

**Battery Price Calculation Algorithm:**
- What's not tested: Complex charging event reconstruction with fragmented data
- Files: `src/interfaces/battery_price_handler.py` (~1223 lines)
- Risk: Incorrect cost attribution; accumulated errors compound
- Priority: **Medium** - Affects billing accuracy but not control safety

**MQTT Integration:**
- What's not tested: Command parsing, state synchronization, error recovery
- Files: `src/interfaces/mqtt_interface.py`
- Risk: Commands silently ignored or misinterpreted; state divergence
- Priority: **Medium** - Impacts user automation scenarios

**Optimization Backend Consistency:**
- What's not tested: Response format compatibility between EOS and EVopt backends
- Files: `src/interfaces/optimization_backends/`
- Risk: Switching backends causes subtle behavioral changes
- Priority: **Medium** - Affects deployment flexibility

---

*Concerns audit: 2026-02-14*
