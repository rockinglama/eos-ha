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

# Price source configuration
CONF_PRICE_SOURCE = "price_source"
CONF_BIDDING_ZONE = "bidding_zone"

PRICE_SOURCE_AKKUDOKTOR = "akkudoktor"
PRICE_SOURCE_ENERGYCHARTS = "energycharts"
PRICE_SOURCE_EXTERNAL = "external"

DEFAULT_BIDDING_ZONE = "DE-LU"

# Default battery values
DEFAULT_BATTERY_CAPACITY = 10.0  # kWh
DEFAULT_MAX_CHARGE_POWER = 5000  # W
DEFAULT_MIN_SOC = 15  # percent
DEFAULT_MAX_SOC = 90  # percent
DEFAULT_INVERTER_POWER = 10000  # W

# Feed-in tariff
CONF_FEED_IN_TARIFF = "feed_in_tariff"
DEFAULT_FEED_IN_TARIFF = 0.082  # EUR/kWh (current DE rate)

# EV (Electric Vehicle) configuration
CONF_EV_ENABLED = "ev_enabled"
CONF_EV_CAPACITY = "ev_capacity"
CONF_EV_CHARGE_POWER = "ev_charge_power"
CONF_EV_SOC_ENTITY = "ev_soc_entity"
CONF_EV_EFFICIENCY = "ev_efficiency"

DEFAULT_EV_CAPACITY = 60.0  # kWh
DEFAULT_EV_CHARGE_POWER = 11000  # W
DEFAULT_EV_EFFICIENCY = 0.95
DEFAULT_EV_MIN_SOC = 10  # %
DEFAULT_EV_MAX_SOC = 100  # %

# Home appliances (flexible loads)
CONF_APPLIANCES = "appliances"

# Battery Storage Price Sensor
CONF_BATTERY_GRID_POWER = "battery_grid_power_entity"
CONF_BATTERY_PV_POWER = "battery_pv_power_entity"
CONF_BATTERY_ENERGY = "battery_energy_entity"
DEFAULT_BATTERY_EFFICIENCY = 0.88

# PV Array configuration
CONF_PV_ARRAYS = "pv_arrays"
DEFAULT_PV_AZIMUTH = 180  # degrees, 180 = south
DEFAULT_PV_TILT = 30  # degrees
DEFAULT_PV_POWER = 5000  # Wp
DEFAULT_PV_INVERTER_POWER = 5000  # W

# SG-Ready heat pump configuration
CONF_SG_READY_ENABLED = "sg_ready_enabled"
CONF_SG_READY_SWITCH_1 = "sg_ready_switch_1"
CONF_SG_READY_SWITCH_2 = "sg_ready_switch_2"

# Temperature entity
CONF_TEMPERATURE_ENTITY = "temperature_entity"

SG_READY_MODES = {
    1: "Lock",
    2: "Normal",
    3: "Recommend",
    4: "Force",
}
