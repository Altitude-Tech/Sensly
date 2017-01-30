# ----------------------------------------------------------------------------
#
# ----------------------------------------------------------------------------

from time import sleep

from smbus import SMBus

import gases

##
#
##
SENSLY_HAT_ADDR = 0x05

##
#
##
MAX_ADC = 4095.0

##
#
##
RLOAD = 10000.0

class BaseSensor:
	##
	#
	##
	_device = None

	##
	#
	##
	_r0 = None

	##
	#
	##
	_rs = None

	##
	#
	##
	_rs_air = None

	##
	#
	##
	_rs_r0_ratio = None

	##
	#
	##
	_adc_value = None

	##
	#
	##
	_cmd = None

	def __init__(self, no_device=False):
		"""
		"""
		if not no_device:
			self_device = SMBus(1)

	@property
	def name(self):
		"""Get the name of the sensor."""
		self.__class__.__name__

	def refresh_data(self):
		"""Get a fresh ADC value from the sensor via the I2C peripheral"""
		if self._device is None:
			return

		self._device.write_byte(SENSLY_HAT_ADDR, self._cmd)

		sleep(0.01)
		data1 = self._device.read_byte(SENSLY_HAT_ADDR)
		sleep(0.01)
		data2 = self.device.read_byte(SENSLY_HAT_ADDR)

		self._adc_value = (data1 << 8) | data2

	def calc_raw_rs_r0_ratio(self):
		"""
		"""
		self._rs_r0_ratio = self.rs / self._r0

	def calc_rs_r0_ratio(self, temperature, humidity):
		"""
		"""
		self.calc_raw_rs_r0_ratio()
		# TODO

	@property
	def rs(self):
		"""
		"""
		return ((MAX_ADC / float(self._adc_value)) - 1) * RLOAD

	@property
	def adc_value(self):
		"""Get the raw ADC value
		"""
		return self._adc_value

	@adc_value.setter
	def adc_value(self, value):
		"""
		"""
		pass

	@property
	def raw_rs_r0_ratio(self):
		"""
		"""
		self.__calc_rs_r0_ratio()
		return self._rs_r0_ratio

	@property
	def rs_r0_ratio(self):
		"""
		"""
		self.correct_rs_r0_ratio()

		return self._rs_r0_ratio

	def gases(self):
		"""
		"""
		pass
