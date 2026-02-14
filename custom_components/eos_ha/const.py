"""Constants for the EOS HA integration."""

DOMAIN = "eos_ha"

# Polling interval
DEFAULT_SCAN_INTERVAL = 300  # 5 minutes in seconds

# External APIs
AKKUDOKTOR_API_URL = "https://api.akkudoktor.net/forecast"
PV_FORECAST_CACHE_HOURS = 6

# Configuration keys
CONF_EOS_URL = "eos_url"
CONF_PRICE_ENTITY = "price_entity"
CONF_SOC_ENTITY = "soc_entity"
CONF_CONSUMPTION_ENTITY = "consumption_entity"
CONF_BATTERY_CAPACITY = "battery_capacity"
CONF_MAX_CHARGE_POWER = "max_charge_power"
CONF_MIN_SOC = "min_soc"
CONF_MAX_SOC = "max_soc"
CONF_INVERTER_POWER = "inverter_power"

# Default battery values
DEFAULT_BATTERY_CAPACITY = 10.0  # kWh
DEFAULT_MAX_CHARGE_POWER = 5000  # W
DEFAULT_MIN_SOC = 10  # percent
DEFAULT_MAX_SOC = 90  # percent
DEFAULT_INVERTER_POWER = 10000  # W
