# Coding Conventions

**Analysis Date:** 2026-02-14

## Naming Patterns

**Files:**
- Lowercase with underscores: `base_control.py`, `battery_interface.py`, `eos_connect.py`
- Test files: `test_*.py` pattern (e.g., `test_control_states.py`, `test_base_control.py`)
- Interface modules: `*_interface.py` suffix (e.g., `battery_interface.py`, `mqtt_interface.py`, `price_interface.py`)

**Classes:**
- PascalCase: `BaseControl`, `BatteryInterface`, `FroniusWR`, `FroniusWRV2`, `ConfigManager`, `MemoryLogHandler`
- Suffixes indicate patterns: `*Interface` for integrations, `*Handler` for processing
- Example: `src/interfaces/base_control.py` → `class BaseControl`

**Functions and Methods:**
- snake_case: `set_current_ac_charge_demand()`, `get_needed_ac_charge_power()`, `was_overall_state_changed_recently()`
- Getter prefix: `get_*` for retrievers (e.g., `get_current_ac_charge_demand()`, `get_override_active_and_endtime()`)
- Setter prefix: `set_*` for mutators (e.g., `set_current_ac_charge_demand()`, `set_current_bat_charge_max()`)
- Private methods: `__method_name` (double underscore) or `_method_name` (single underscore)
- Example: `__fetch_soc_data_unified()`, `__start_update_service()`, `_handle_soc_error()`

**Variables and Constants:**
- snake_case for local/instance variables: `current_ac_charge_demand`, `soc_fail_count`, `time_frame_base`
- SCREAMING_SNAKE_CASE for module-level constants: `MODE_CHARGE_FROM_GRID`, `MODE_AVOID_DISCHARGE`, `TEMP_COMPENSATION_SENSITIVITY`
- Prefix for private/internal: `_private_var`, `__double_underscore_var`
- Examples in `src/interfaces/base_control.py`:
  - `MODE_CHARGE_FROM_GRID = 0` (constant)
  - `self.current_ac_charge_demand = 0` (instance variable)
  - `self._state_change_timestamps = []` (protected list)

**Module-Level State:**
- Logger per module: `logger = logging.getLogger("__main__")`
- Config/setup at module level: `config_manager = ConfigManager(current_dir)`, `time_zone = pytz.timezone(...)`

## Code Style

**Formatting:**
- No explicit formatter configured (no `.prettierrc`, `black` config, or `isort`)
- Style appears to follow PEP 8 conventions
- String formatting: Mix of `%` formatting and f-strings
  - Example: `logger.info("[BASE-CTRL] loading module ")`
  - Example: `f"AC charge should be limited to {max_grid}W"`
- Indentation: 4 spaces (standard Python)

**Linting:**
- Uses `pylint` directives in tests: `# pylint: disable=protected-access` (comments indicate white-box testing practice)
- No `.eslintrc` or `pylint.rc` found in repo

**Line Length:**
- Varies; no strict limit enforced. Lines can exceed 80-100 characters.
- Long imports organized vertically when needed

## Import Organization

**Order:**
1. Standard library imports (logging, os, sys, datetime, json, etc.)
2. Third-party imports (requests, pytz, pandas, flask, gevent, etc.)
3. Local imports (from config import, from interfaces import, from version import)

**Path Aliases:**
- No aliases detected; relative imports used within packages
- Example from `src/eos_connect.py`:
  ```python
  from version import __version__
  from config import ConfigManager
  from interfaces.base_control import BaseControl
  from interfaces.battery_interface import BatteryInterface
  ```

**Barrel Files:**
- Not heavily used; most imports are direct from individual modules

## Error Handling

**Patterns:**
- Explicit exception catching by type: `except requests.exceptions.Timeout:`, `except requests.exceptions.RequestException as e:`
- Multiple exception types in single handler: `except (ValueError, KeyError) as e:`
- Try-except blocks wrap external API calls and file I/O
- Custom error handling methods: `_handle_soc_error()` in `src/interfaces/battery_interface.py` (lines 289-296)
- Errors logged before returning fallback values
  - Example from line 290-291 in `battery_interface.py`:
    ```python
    except requests.exceptions.Timeout:
        return self._handle_soc_error(self.src, "Request timed out", self.current_soc)
    ```

**Exception Types Caught:**
- `requests.exceptions.RequestException` - HTTP/network errors
- `requests.exceptions.Timeout` - API timeouts
- `ValueError` - Value conversion errors
- `KeyError` - Dictionary key missing errors
- `TypeError` - Type mismatches
- Custom `ValueError` with descriptive messages for config validation

**Fallback Strategy:**
- Return last known good value on error
- Log error at WARNING or ERROR level
- Track failure counts (`self.soc_fail_count`) to avoid repeated errors
- Example: battery interface returns `self.current_soc` when fetch fails

## Logging

**Framework:** `logging` (Python standard library)

**Patterns:**
- Module logger: `logger = logging.getLogger("__main__")`
- Prefixed log messages with module identifier: `[BASE-CTRL]`, `[BATTERY-IF]`, `[MAIN]`, `[Config]`
- Example: `logger.info("[BASE-CTRL] loading module ")`
- Log levels: DEBUG, INFO, WARNING, ERROR based on severity
- Configurable via `log_level` in config.yaml (line 86 of `src/eos_connect.py`)
- Custom timezone formatter: `TimezoneFormatter` in `src/eos_connect.py` (lines 45-57)

**When to Log:**
- Module load: `logger.info("[...] loading module")`
- State changes: `logger.debug("[...] state changed to...")`
- Errors/exceptions: `logger.error("[...] Error description")`
- Configuration issues: `logger.warning("[Config] Invalid setting...")`

## Comments

**When to Comment:**
- Complex algorithms with multiple steps (e.g., battery charge limiting logic in test files)
- Non-obvious calculations or edge cases
- Configuration/tuning guidance: See `src/interfaces/battery_interface.py` lines 49-67 (temperature compensation explanation)
- Issue references: Test docstrings reference GitHub issues (e.g., "GitHub Issue #167" in `test_base_control.py`)

**JSDoc/Docstring:**
- Module-level docstrings present in all files
- Class docstrings: Triple-quoted descriptions of purpose and usage
- Method docstrings: Describe purpose, parameters, and return values
- Example from `src/interfaces/base_control.py`:
  ```python
  def get_state_mapping(self, num_mode):
      """
      Returns the state mapping dictionary.
      """
      return state_mapping.get(num_mode, "unknown state")
  ```
- Test docstrings document specific test cases and scenarios
- No type hints found (Python 3.11+ but not using annotations)

## Function Design

**Size:**
- Range: 5-50 lines typically
- Getter/setter methods: 2-5 lines
- Complex methods: 15-30 lines (e.g., `__fetch_soc_data_unified()` with 50+ lines for sophisticated SOC format detection)

**Parameters:**
- Self for methods + positional params + optional keyword args
- Example: `def set_current_ac_charge_demand(self, value_relative):`
- Methods with side effects accept values to set/update
- Getter methods take no parameters (aside from self)
- Initialization: accept config dict and dependencies
  - Example: `def __init__(self, config, timezone, time_frame_base):`

**Return Values:**
- Getters return single values or tuples
- Setters return None (implicit)
- Methods raising errors for invalid input (with try-except in caller)
- Fallback returns on error: return cached/safe value
- Example: `get_max_charge_power_dyn()` returns float (W)

## Module Design

**Exports:**
- Class-based modules export primary class + any constants
- `src/interfaces/base_control.py` exports: `BaseControl` class + mode constants (`MODE_CHARGE_FROM_GRID`, etc.)
- `src/config.py` exports: `ConfigManager` class
- Helper classes/functions exported alongside primary class where related

**Organization:**
- One main class per module (sometimes with helper classes)
- Constants defined at module level before class
- Module-level logger initialized early
- Initialization code at module level for critical setup (`src/eos_connect.py` lines 83-99)

**Patterns:**
- Background threads managed via `_update_thread` and `_stop_event`
- Singleton-like usage: `config_manager = ConfigManager(...)` instantiated once at module level
- State objects passed via composition (e.g., `base_control` passed to `battery_interface`)
- Private methods named with `__` for true encapsulation (e.g., `__fetch_soc_data_unified()`)

---

*Convention analysis: 2026-02-14*
