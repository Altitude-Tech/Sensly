# ----------------------------------------------------------------------------
#
# ----------------------------------------------------------------------------

import sensors

mq2 = sensors.SensorMQ2(no_device=True)

mq2.adc_value = 1234
mq2.calc_rs_r0_ratio()

for gas in mq2.gases():
	print gas

