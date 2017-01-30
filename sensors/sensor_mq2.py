# ----------------------------------------------------------------------------
#
# ----------------------------------------------------------------------------

from base_sensor import BaseSensor
import gases

class SensorMQ2(BaseSensor):
	##
	#
	##
	_r0 = 3120.5010
	_rs_air = 9.5
	_cmd = 0x01

	##
	#
	##
	_config_alcohol = {}
	_config_ch4 = {}
	_config_co = {}
	_config_h2 = {}
	_config_lpg = {}
	_config_propane = {}

	_gas_config = {
		gases.GAS_ALCOHOL: self._config_alcohol,
		gases.GAS_CH4: self._config_ch4,
		gases.GAS_CO: self._config_co,
		gases.GAS_H2: self._config_h2,
		gases.GAS_LPG: self._config_lpg,
		gases.GAS_PROPANE: self._config_propane
	}
