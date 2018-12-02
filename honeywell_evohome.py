"""
Support for Honeywell Evohome thermostats.
"""
import logging
import socket
import datetime

import requests
import voluptuous as vol

import homeassistant.helpers.config_validation as cv
from homeassistant.components.climate import (
    ClimateDevice, PLATFORM_SCHEMA, ATTR_FAN_MODE, ATTR_FAN_LIST,
    ATTR_OPERATION_MODE, ATTR_OPERATION_LIST, SUPPORT_TARGET_TEMPERATURE,
    SUPPORT_OPERATION_MODE)
from homeassistant.const import (
    CONF_PASSWORD, CONF_USERNAME, TEMP_CELSIUS, TEMP_FAHRENHEIT,
    ATTR_TEMPERATURE)


REQUIREMENTS = ['evohomeclient==0.2.5']

_LOGGER = logging.getLogger(__name__)

ATTR_FAN = 'fan'
ATTR_SYSTEM_MODE = 'system_mode'
ATTR_CURRENT_OPERATION = 'equipment_output_status'

CONF_AWAY_TEMPERATURE = 'away_temperature'
CONF_COOL_AWAY_TEMPERATURE = 'away_cool_temperature'
CONF_HEAT_AWAY_TEMPERATURE = 'away_heat_temperature'

DEFAULT_AWAY_TEMPERATURE = 16
DEFAULT_COOL_AWAY_TEMPERATURE = 30
DEFAULT_HEAT_AWAY_TEMPERATURE = 16


PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_USERNAME): cv.string,
    vol.Required(CONF_PASSWORD): cv.string,
    vol.Optional(CONF_AWAY_TEMPERATURE,
                 default=DEFAULT_AWAY_TEMPERATURE): vol.Coerce(float),
    vol.Optional(CONF_COOL_AWAY_TEMPERATURE,
                 default=DEFAULT_COOL_AWAY_TEMPERATURE): vol.Coerce(float),
    vol.Optional(CONF_HEAT_AWAY_TEMPERATURE,
                 default=DEFAULT_HEAT_AWAY_TEMPERATURE): vol.Coerce(float),
})

STATE_AUTO = 'Auto'
STATE_ECO = 'AutoWithEco'
STATE_AWAY = 'Away'
STATE_DAYOFF = 'DayOff'
STATE_CUSTOM = 'Custom'
STATE_OFF = 'HeatingOff'

EVOHOME_STATE_MAP = {
    'AUTO_MODE': STATE_AUTO,
    'ECO_MODE': STATE_ECO,
    'AWAY_MODE': STATE_AWAY,
    'DAYOFF_MODE': STATE_DAYOFF,
    'CUSTOM_MODE': STATE_CUSTOM,
    'OFF_MODE' : STATE_OFF
}


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Set up the Honeywell thermostat."""
    username = config.get(CONF_USERNAME)
    password = config.get(CONF_PASSWORD)

    return _setup_round(username, password, config, add_devices)


def _setup_round(username, password, config, add_devices):
    """Set up the rounding function."""
    from evohomeclient2 import EvohomeClient

    away_temp = config.get(CONF_AWAY_TEMPERATURE)
    client = EvohomeClient(username, password)

    try:
        for device in client.temperatures():
            add_devices([RoundThermostat(client, device['id'], True, 10)], True)
    except socket.error:
        _LOGGER.error(
            "Connection error logging into the honeywell evohome web service")
        return False
    return True


class RoundThermostat(ClimateDevice):
    """Representation of a Honeywell Round Connected thermostat."""

    def __init__(self, client, zone_id, master, away_temp):
        """Initialize the thermostat."""
        self.client = client
        self._current_temperature = None
        self._target_temperature = None
        self._name = 'round connected'
        self._id = zone_id
        self._master = master
        self._is_dhw = False
        self._away_temp = away_temp
        self._away = False


    @property
    def supported_features(self):
        """Return the list of supported features."""
        supported = (SUPPORT_TARGET_TEMPERATURE)
        if hasattr(self.client, ATTR_SYSTEM_MODE):
            supported |= SUPPORT_OPERATION_MODE
        return supported

    @property
    def name(self):
        """Return the name of the honeywell, if any."""
        return self._name

    @property
    def temperature_unit(self):
        """Return the unit of measurement."""
        return TEMP_CELSIUS

    @property
    def current_temperature(self):
        """Return the current temperature."""
        return self._current_temperature

    @property
    def target_temperature(self):
        """Return the temperature we try to reach."""
        if self._is_dhw:
            return None
        return self._target_temperature

    @property
    def operation_list(self):
        """Return the list of available operation modes."""
        op_list = []

        for mode in EVOHOME_STATE_MAP:
            op_list.append(EVOHOME_STATE_MAP.get(mode))

        return op_list


    def set_temperature(self, **kwargs):
        """Set new target temperature."""
        temperature = kwargs.get(ATTR_TEMPERATURE)
        if temperature is None:
            return
        zone = self.client.locations[0]._gateways[0]._control_systems[0].zones[self._name]
        zone.set_temperature(temperature)

    @property
    def current_operation(self: ClimateDevice) -> str:
        """Get the current operation of the system."""
        return getattr(self.client, ATTR_SYSTEM_MODE, None)

    @property
    def is_away_mode_on(self):
        """Return true if away mode is on."""
        return self._away

    def set_operation_mode(self: ClimateDevice, operation_mode: str) -> None:
        """Set the HVAC mode for the thermostat."""

        functions = {
            'Auto': self.client.set_status_normal,
            'AutoWithEco': self.client.set_status_eco,
            'Away': self.client.set_status_away,
            'DayOff': self.client.set_status_dayoff,
            'Custom': self.client.set_status_custom,
            'HeatingOff': self.client.set_status_heatingoff
            }

        func = functions[operation_mode]
        func()

    def turn_away_mode_on(self):
        """Turn away on.
        Honeywell does have a proprietary away mode, but it doesn't really work
        the way it should. For example: If you set a temperature manually
        it doesn't get overwritten when away mode is switched on.
        """
        self._away = True
        self.client.set_status_away() # Heating and hot water off

    def turn_away_mode_off(self):
        """Turn away off."""
        self._away = False
        self.client.set_status_normal()

    def update(self):
        """Get the latest date."""
        try:
            # Only refresh if this is the "master" device,
            # others will pick up the cache
            for val in self.client.temperatures():
                if val['id'] == self._id:
                    data = val

        except KeyError:
            _LOGGER.error("Update failed from Honeywell server")
            self.client.user_data = None
            return

        except StopIteration:
            _LOGGER.error("Did not receive any temperature data from the evohomeclient API")
            return

        self._current_temperature = data['temp']
        self._target_temperature = data['setpoint']
        if data['thermostat'] == 'DOMESTIC_HOT_WATER':
            self._name = 'Hot Water'
            self._is_dhw = True
        else:
            self._name = data['name']
            self._is_dhw = False

            status=self.client.locations[0].status()
            tcs=status['gateways'][0]['temperatureControlSystems'][0]
            currentmode=tcs['systemModeStatus']['mode']
            self.client.system_mode = currentmode
            #_LOGGER.error(status)