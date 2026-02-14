# Testing Patterns

**Analysis Date:** 2026-02-14

## Test Framework

**Runner:**
- pytest (Python testing framework)
- No explicit `pytest.ini` or `setup.cfg` found; configuration likely minimal
- Tests invoked via `pytest tests/` pattern

**Assertion Library:**
- pytest built-in assertions with `assert` statements
- `pytest.approx()` for floating-point comparisons (e.g., `assert value == pytest.approx(0.002)`)
- `pytest.raises()` context manager for exception testing

**Run Commands:**
```bash
pytest                                # Run all tests
pytest tests/test_control_states.py   # Run specific test file
pytest tests/interfaces/               # Run tests in subdirectory
pytest -v                              # Verbose output
pytest -s                              # Show print statements
pytest::ClassName::method              # Run specific test method
python -m pytest                       # Alternative invocation
```

## Test File Organization

**Location:**
- Tests in `tests/` directory parallel to `src/`
- Co-located pattern: `src/interfaces/base_control.py` → `tests/interfaces/test_base_control.py`
- Subdirectory structure mirrors source: `tests/interfaces/`, `tests/interfaces/optimization_backends/`

**Naming:**
- Test files: `test_*.py` prefix (e.g., `test_control_states.py`, `test_battery_interface.py`)
- Test classes: `Test*` prefix (e.g., `TestGridChargeLimiting`, `TestACChargeDemandConversion`)
- Test methods: `test_*` prefix (e.g., `test_hourly_intervals_at_start_of_hour()`)
- Descriptive names matching scenario: `test_ac_charge_respects_max_grid_charge_rate()`

**Structure:**
```
tests/
├── test_control_states.py                              # Root-level test
├── interfaces/
│   ├── test_base_control.py                            # Specific module tests
│   ├── test_battery_interface.py
│   ├── test_load_interface.py
│   ├── test_price_interface.py
│   ├── test_pv_interface.py
│   ├── test_inverter_fronius_v2.py
│   ├── test_optimization_interface.py
│   ├── test_battery_price_handler.py
│   └── optimization_backends/
│       └── test_optimization_backend_eos.py
```

## Test Structure

**Suite Organization:**
```python
class TestGridChargeLimiting:
    """Test suite for max_grid_charge_rate limiting"""

    @patch("src.interfaces.base_control.datetime")
    def test_ac_charge_respects_max_grid_charge_rate(
        self, mock_datetime, config_zendure, berlin_timezone
    ):
        """
        Test that AC charge power is limited by max_grid_charge_rate.
        User's case: ...
        """
        # Setup
        mock_now = berlin_timezone.localize(datetime(2025, 1, 1, 10, 0, 0))
        mock_datetime.now.return_value = mock_now

        # Exercise
        base_control = BaseControl(config_zendure, berlin_timezone, time_frame_base=3600)
        base_control.set_current_ac_charge_demand(1.0)
        base_control.set_current_bat_charge_max(2000)
        needed_ac_power = base_control.get_needed_ac_charge_power()

        # Verify
        assert needed_ac_power == 2000, "BaseControl returns 2000W (battery limit)"
```

**Patterns:**

1. **Setup Phase:**
   - Fixtures provide config dictionaries and timezone objects
   - Mocks injected via decorators: `@patch("src.interfaces.base_control.datetime")`
   - Mock objects configured: `mock_datetime.now.return_value = mock_now`

2. **Teardown Phase:**
   - No explicit teardown in most tests
   - Long-lived objects (interfaces) explicitly shutdown in fixtures:
     ```python
     bi.shutdown()  # From test_battery_interface.py line 134
     ```

3. **Assertion Pattern:**
   - Direct assertions: `assert value == expected, "descriptive message"`
   - Multi-line assertions with context: `assert condition, f"got {actual}, expected {expected}"`
   - Pytest special assertions: `assert value == pytest.approx(0.002)`

## Test Structure Examples

**Fixture Pattern (Config-driven):**
```python
@pytest.fixture
def config_zendure():
    """Configuration matching the user's Zendure Solarflow 800 Pro setup"""
    return {
        "battery": {
            "max_charge_power_w": 2000,
            "capacity_wh": 10000,
            "max_soc_percentage": 100,
            "charge_efficiency": 0.95,
            "discharge_efficiency": 0.95,
            "price_euro_per_wh_accu": 0.0001,
        },
        "inverter": {
            "type": "default",
            "max_grid_charge_rate": 1000,
            "max_pv_charge_rate": 2000,
        },
    }

@pytest.fixture
def berlin_timezone():
    """Timezone fixture"""
    return pytz.timezone("Europe/Berlin")
```

**Mock Pattern (Datetime mocking):**
```python
@patch("src.interfaces.base_control.datetime")
def test_scenario(self, mock_datetime, config_base, berlin_timezone):
    mock_now = berlin_timezone.localize(datetime(2025, 1, 1, 10, 0, 0))
    mock_datetime.now.return_value = mock_now
```

**Monkeypatch Pattern (API response mocking):**
```python
def fake_get(url, headers=None, timeout=None):
    assert url.startswith(expected_url)
    return DummyResponse(sample_payload)

monkeypatch.setattr(
    "src.interfaces.price_interface.requests.get",
    fake_get,
)
```

**Dummy Response Pattern:**
```python
class DummyResponse:
    """Minimal requests.Response stub for tests."""

    def __init__(self, payload):
        self._payload = payload

    def raise_for_status(self):
        return None

    def json(self):
        return self._payload
```

## Mocking

**Framework:** `unittest.mock` (Python standard library)
- `@patch()` decorator for module-level mocks
- `MagicMock()` for simulating objects with call tracking
- `monkeypatch` pytest fixture for attribute replacement

**Patterns:**

1. **Datetime mocking** (lines 49, 71, 114 in `test_control_states.py`):
   ```python
   @patch("src.interfaces.base_control.datetime")
   def test_scenario(self, mock_datetime, config, timezone):
       mock_now = timezone.localize(datetime(2025, 1, 1, 10, 0, 0))
       mock_datetime.now.return_value = mock_now
   ```

2. **HTTP Request mocking** (test_battery_interface.py line 66):
   ```python
   with patch("src.interfaces.battery_interface.requests.get") as mock_get:
       mock_resp = MagicMock()
       mock_resp.json.return_value = {"state": "80"}
       mock_resp.raise_for_status.return_value = None
       mock_get.return_value = mock_resp
   ```

3. **Monkeypatch for complex setup** (test_price_interface.py line 97):
   ```python
   monkeypatch.setattr(
       "src.interfaces.price_interface.requests.get",
       fake_get,
   )
   ```

**What to Mock:**
- External API calls (requests, OpenHAB, Home Assistant, EVCC)
- System time/datetime (for deterministic scheduling tests)
- Long-running operations (_update_thread, background services)
- Configuration sources

**What NOT to Mock:**
- Business logic being tested (BaseControl, BatteryInterface methods)
- Core calculations (charge power limits, SOC format detection)
- Simple data structures (dicts, lists)

## Fixtures and Factories

**Test Data Pattern:**
```python
@pytest.fixture
def default_config():
    """Returns a default configuration dictionary for BatteryInterface."""
    return {
        "source": "default",
        "url": "",
        "soc_sensor": "",
        "max_charge_power_w": 3000,
        "capacity_wh": 10000,
        "min_soc_percentage": 10,
        "max_soc_percentage": 90,
        "charging_curve_enabled": True,
        "discharge_efficiency": 1.0,
        "price_euro_per_wh_accu": 0.0,
        "price_euro_per_wh_sensor": "",
    }
```

**Custom Fixtures:**
```python
@pytest.fixture
def config_base():
    """Base configuration for tests"""
    return {
        "battery": {...},
        "inverter": {...},
    }

@pytest.fixture
def berlin_timezone():
    """Timezone fixture"""
    return pytz.timezone("Europe/Berlin")
```

**Location:**
- Fixtures defined in test files themselves (no separate `conftest.py` found)
- Shared fixtures repeated across test files
- Each test file is self-contained with its own fixtures

## Coverage

**Requirements:**
- No coverage requirement detected in config
- No `.coveragerc` found
- Tests written to specific scenarios rather than 100% coverage goal

**View Coverage:**
```bash
pytest --cov=src/
pytest --cov=src/ --cov-report=html
pytest --cov=src/interfaces/base_control.py
```

## Test Types

**Unit Tests:**
- Scope: Individual classes and methods
- Approach: Mock external dependencies, focus on business logic
- Examples:
  - `test_ac_charge_respects_max_grid_charge_rate()` - Tests charge limiting logic in isolation
  - `test_init_sets_attributes()` - Tests object initialization
  - `test_default_source_sets_soc_to_5()` - Tests default behavior

**Integration Tests:**
- Scope: Multiple components working together
- Approach: Create real objects, mock only external APIs
- Examples:
  - `test_ac_charge_not_limited_when_below_grid_rate()` - Tests interactions between charge demand and limiting logic
  - `test_zendure_solarflow_scenario()` - Tests combined AC+DC charging with both limits
  - Battery interface tests with mocked HTTP but real config parsing

**E2E Tests:**
- Framework: Not detected
- Status: Not used (no `e2e/` directory, no Selenium/browser automation)

## Common Patterns

**Async Testing:**
- Pattern: Not used (no async/await in codebase)
- Threading tested via `_update_thread` attributes in some interfaces, but threads started in background

**Error Testing:**
```python
@pytest.fixture
def config_standard():
    """Standard configuration with equal limits"""
    return {...}

@patch("src.interfaces.base_control.datetime")
def test_invalid_state_raises_error(self, mock_datetime, config_standard, berlin_timezone):
    """Test that invalid state names raise an error"""
    base_control = BaseControl(config_standard, berlin_timezone, time_frame_base=3600)

    # Setup validation if not implemented
    valid_states = ["auto", "charge", "discharge", "idle"]

    def change_state(state):
        if state not in valid_states:
            raise ValueError(f"Invalid state: {state}")
        base_control._control_state = state

    base_control.change_control_state = change_state

    # Test exception is raised
    with pytest.raises(ValueError):
        base_control.change_control_state("invalid_state")
```

**Boundary Testing:**
```python
def test_zero_charge_demand(self, mock_datetime, config_zendure, berlin_timezone):
    """Test with zero charge demand"""
    # ...
    base_control.set_current_ac_charge_demand(0.0)
    base_control.set_current_bat_charge_max(0)
    needed_ac_power = base_control.get_needed_ac_charge_power()
    assert needed_ac_power == 0, "Zero charge demand should result in 0W"

def test_all_limits_equal(self, mock_datetime, config_standard, berlin_timezone):
    """Test when all limits are equal (most common case)"""
    # ...
```

**Parametrized Tests:**
- Pattern: Not heavily used
- Alternative: Multiple specific test methods instead (e.g., `test_15min_intervals_at_start_of_slot()` + `test_hourly_intervals_at_start_of_hour()`)

**State Machine Testing:**
```python
class TestControlStateTransitions:
    """Test suite for change_control_state functionality"""

    def test_initial_state_is_auto(...):
        """Test that initial control state is 'auto'"""

    def test_state_transition_chain(...):
        """Test multiple state transitions in sequence"""
        states = ["auto", "charge", "discharge", "idle", "auto"]
        for state in states:
            base_control.change_control_state(state)
            assert base_control.get_control_state() == state
```

## Test Naming & Documentation

**Docstrings:**
- All test methods have docstrings explaining the test scenario
- Docstrings often include user context (e.g., "User's case: Battery allows 2000W, Grid limit is 1000W")
- Example from line 75 of `test_control_states.py`:
  ```python
  def test_ac_charge_respects_max_grid_charge_rate(
      self, mock_datetime, config_zendure, berlin_timezone
  ):
      """
      Test that AC charge power is limited by max_grid_charge_rate.

      User's case:
      - Battery allows 2000W
      - Grid limit is 1000W
      - Result should be 1000W, not 2000W
      """
  ```

**Test Hierarchy:**
- Root test file: `tests/test_control_states.py` - high-level scenarios
- Interface tests: `tests/interfaces/test_*.py` - component-specific
- Backend tests: `tests/interfaces/optimization_backends/` - specific implementations

## Notable Testing Practices

1. **Issue-Driven Tests:** Tests reference specific GitHub issues
   - Example: `test_issue_167_mqtt_inverter_parity()` addresses Issue #167 (AC charge conversion)

2. **User Scenario Tests:** Tests include real-world device configurations
   - Example: `config_zendure` matches Zendure Solarflow 800 Pro specs

3. **Descriptive Assertions:** Assert messages provide context
   - Example: `assert tgt_ac_charge_power == 1000, f"AC charge should be limited to max_grid_charge_rate (1000W), got {tgt_ac_charge_power}W"`

4. **Defensive Fixture Setup:** Tests check if methods exist before using them
   - Example (line 427 of test_control_states.py):
     ```python
     if not hasattr(base_control, "get_control_state"):
         base_control._control_state = "auto"
         base_control.get_control_state = lambda: base_control._control_state
     ```

---

*Testing analysis: 2026-02-14*
