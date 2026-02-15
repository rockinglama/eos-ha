"""Constants for the EOS HA integration."""

DOMAIN = "eos_ha"

# Polling interval
DEFAULT_SCAN_INTERVAL = 300  # 5 minutes in seconds

# Configuration keys
CONF_EOS_URL = "eos_url"
CONF_PRICE_ENTITY = "price_entity"
CONF_SOC_ENTITY = "soc_entity"
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

# Load prediction
CONF_YEARLY_CONSUMPTION = "yearly_consumption"
DEFAULT_YEARLY_CONSUMPTION = 12000  # kWh

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
CONF_SG_READY_SURPLUS_THRESHOLD = "sg_ready_surplus_threshold"
DEFAULT_SG_READY_SURPLUS_THRESHOLD = 500  # W

# Energy meter entities (for EOS HA Adapter)
CONF_LOAD_EMR_ENTITY = "load_emr_entity"
CONF_GRID_IMPORT_EMR_ENTITY = "grid_import_emr_entity"
CONF_GRID_EXPORT_EMR_ENTITY = "grid_export_emr_entity"
CONF_PV_PRODUCTION_EMR_ENTITY = "pv_production_emr_entity"

# EOS solution entity IDs (written by EOS HA Adapter, read by our wrapper sensors)
EOS_ENTITY_AC_CHARGE = "sensor.eos_genetic_ac_charge_factor"
EOS_ENTITY_DC_CHARGE = "sensor.eos_genetic_dc_charge_factor"
EOS_ENTITY_DISCHARGE_ALLOWED = "sensor.eos_genetic_discharge_allowed_factor"
EOS_ENTITY_BATTERY_SOC = "sensor.eos_battery1_soc_factor"
EOS_ENTITY_COSTS = "sensor.eos_costs_amt"
EOS_ENTITY_REVENUE = "sensor.eos_revenue_amt"
EOS_ENTITY_GRID_CONSUMPTION = "sensor.eos_grid_consumption_energy_wh"
EOS_ENTITY_GRID_FEEDIN = "sensor.eos_grid_feedin_energy_wh"
EOS_ENTITY_LOAD = "sensor.eos_load_energy_wh"
EOS_ENTITY_LOSSES = "sensor.eos_losses_energy_wh"
EOS_ENTITY_BATTERY1 = "sensor.eos_battery1"
EOS_ENTITY_DATETIME = "sensor.eos_date_time"

SG_READY_MODES = {
    1: "Lock",
    2: "Normal",
    3: "Recommend",
    4: "Force",
}
