import smbus 
import subprocess
from time import *

import RPi.GPIO as GPIO
from Sensors import Sensor, Gas
from bme_combo import *
import logging
import sys


# Sensly Constants 
WARM_UP_TIMEOUT = 3 # 600 by AltitudeTech
R0 = [3120.5010, 1258.8822, 2786.3375]      # MQ2, MQ7, MQ135 R0 resistance (needed for PPM calculation).
                                            # Found by placing the Sensor in a clean air environment and running the calibration script
RSAir = [9.5,27,3.62]                       # Sensor RS/R0 ratio in clean air

LED = [0xFF, 0x00, 0x00]                    # Set LED to Red 

MQ2 = Sensor('MQ2',R0[0],RSAir[0])          # name, Calibrated R0 value, RSAir value 
MQ7 = Sensor('MQ7',R0[1],RSAir[1])
MQ135 = Sensor('MQ135',R0[2],RSAir[2])
PM = Sensor('PM',0,0)

# Constants for temperature and humididty correction
MQ2_t_30H = [-0.00000072,0.00006753,-0.01530561,1.5594955]
MQ2_t_60H = [-0.00000012,0.00003077,-0.01287521,1.32473027]
MQ2_t_85H = [-0.00000033,0.00004116,-0.01135847,1.14576424]

MQ7_t_33H = [-0.00001017,0.00076638,-0.01894577,1.1637335]
MQ7_t_85H = [-0.00000481,0.0003916,-0.01267189,0.99930744]

MQ135_t_33H = [-0.00000042,0.00036988,-0.02723828,1.40020563]
MQ135_t_85H = [-0.0000002,0.00028254,-0.02388492,1.27309524]

#Sensors commands
MQ2cmd = 0x01
MQ7cmd = 0x02
MQ135cmd = 0x03
PMcmd = 0x04

#Gases variables
COPPM = 0
NH4PPM = 0
CO2PPM = 0
CO2H50HPPM = 0
CH3PPM = 0
CH3_2COPPM = 0
AlchPPM = 0
CH4PPM = 0
LPGPPM = 0
H2PPM = 0
PropPPM = 0

MQ2_H2 = Gas('MQ2_H2', 0.3222, -0.4750, -2.0588, 3.017, 100, LED) # name, rs_r0_ratio max value, rs_r0_ratio max value, gas conversion formula gradient, gas conversion formula intercept, threshold, LED Colour
MQ2_LPG = Gas('MQ2_LPG', 0.2304, -0.5850, -2.0626, 2.808, 1000, LED)
MQ2_CH4 = Gas('MQ2_CH4', 0.4771, -0.1612, -2.6817, 3.623, 1000, LED)
MQ2_CO = Gas('MQ2_CO', 0.7160, 0.204, -3.2141, 4.624, 30, LED)
MQ2_Alch = Gas('MQ2_Alcohol', 0.4624, -0.1804,-2.7171, 3.5912, 1000, LED)
MQ2_Prop = Gas('MQ2_Propane', 0.2553, -0.5528,-2.0813, 2.8436, 1000, LED)

MQ7_Alch = Gas('MQ7_Alcohol', 1.2304, 1.1139, -15.283, 20.415, 1000, LED)
MQ7_CH4 = Gas('MQ7_CH4', 1.1761, 0.9542, -8.6709, 12.024, 1000, LED)
MQ7_LPG = Gas('MQ7_LPG', 0.9420, 0.6901, -7.6181, 8.8335, 1000, LED)
MQ7_CO = Gas('MQ7_CO', 0.2175, -1.0458, -1.5096, 2.0051, 30, LED)
MQ7_H2 = Gas('MQ7_H2', 0.1303, -1.2757, -1.3577, 1.8715, 100, LED)

MQ135_CO = Gas('MQ135_CO', 0.4548, 0.1584, -4.272, 2.9347, 100, LED)
MQ135_NH4 = Gas('MQ135_NH4', 0.4133, -0.1135, -2.4562, 2.0125, 500, LED)
MQ135_CO2 = Gas('MQ135_CO2', 0.3711, -0.0969, -2.7979, 2.0425, 5000, LED)
MQ135_Ethan = Gas('MQ135_Ethanol', 0.2810, -0.1337, -3.1616, 1.8939, 1000, LED)
MQ135_Methly = Gas('MQ135_Methly', 0.2068, -0.1938, -3.2581, 1.6759, 1000, LED)
MQ135_Acet = Gas('MQ135_Acetone', 0.1790, -0.2328, -3.1878, 1.577, 100, LED)

#Variables
logger = None
temp_hum_sensor = BME280(mode=BME280_OSAMPLE_8)

#functions

def Reset():
	GPIO.setmode(GPIO.BCM) ## Use BCM numbering
	GPIO.setup(23, GPIO.OUT)

	# Reset Sensly HAT
	GPIO.output(23, False) ## Set GPIO Pin 23 to low
	time.sleep(0.5)
	GPIO.output(23, True) ## Set GPIO Pin 23 to High
	# Clean up the GPIO pins 
	GPIO.cleanup()

def get_i2cdetect():
	command = "i2cdetect -y 1"
	try:
		p = subprocess.Popen(command, shell=True, stdout=subprocess.PIPE)
		for line in p.stdout.readlines():
			logger.info("Command result line:%s" % line)
		result = p.wait()
		logger.info("I2cdetect value is:%s" % result)
	except Exception:
		logger.exception("Exception in popen with command %s" % command)
		raise
	print result

def init_logger():
	"""
	 Initializes the logger
	"""           
	global logger
	logging.basicConfig(stream=sys.stdout, level=logging.DEBUG, format='%(asctime)s.%(msecs)03d %(levelname)s %(module)s - %(funcName)s: %(message)s', datefmt="%Y-%m-%d %H:%M:%S")
	logger = logging.getLogger(__name__)
	logger.debug("start of script")
  
def Get_MQ2PPM(MQ2Rs_R0, Gases = []):
	"""
	This Function checks the RS/R0 value to select which gas is being detected
		modifies Gases parameter
	"""
	if MQ2Rs_R0 <= 5.2 and MQ2Rs_R0 > 3:
		Gases[0] = MQ2_CO.Get_PPM(MQ2Rs_R0)
		Gases[1] = 0
		Gases[2] = 0
		Gases[3] = 0
		Gases[4] = 0
		Gases[5] = 0
	elif MQ2Rs_R0 <=3 and MQ2Rs_R0 > 2.85:
		Gases[0] = MQ2_CO.Get_PPM(MQ2Rs_R0)
		Gases[1] = MQ2_CH4.Get_PPM(MQ2Rs_R0)
		Gases[2] = 0
		Gases[3] = 0
		Gases[4] = 0
		Gases[5] = 0
	elif MQ2Rs_R0 <=2.85 and MQ2Rs_R0 > 2.1:
		Gases[0] = MQ2_CO.Get_PPM(MQ2Rs_R0)
		Gases[1] = MQ2_CH4.Get_PPM(MQ2Rs_R0)
		Gases[2] = MQ2_Alch.Get_PPM(MQ2Rs_R0)
		Gases[3] = 0
		Gases[4] = 0
		Gases[5] = 0
	elif MQ2Rs_R0 <= 2.1 and MQ2Rs_R0 > 1.8:
		Gases[0] = MQ2_CO.Get_PPM(MQ2Rs_R0)
		Gases[1] = MQ2_CH4.Get_PPM(MQ2Rs_R0)
		Gases[2] = MQ2_Alch.Get_PPM(MQ2Rs_R0)
		Gases[3] = MQ2_H2.Get_PPM(MQ2Rs_R0)
		Gases[4] = 0
		Gases[5] = 0
	elif MQ2Rs_R0 <= 1.8 and MQ2Rs_R0 > 1.6:
		Gases[0] = MQ2_CO.Get_PPM(MQ2Rs_R0)
		Gases[1] = MQ2_CH4.Get_PPM(MQ2Rs_R0)
		Gases[2] = MQ2_Alch.Get_PPM(MQ2Rs_R0)
		Gases[3] = MQ2_H2.Get_PPM(MQ2Rs_R0)
		Gases[4] = MQ2_Prop.Get_PPM(MQ2Rs_R0)
		Gases[5] = MQ2_LPG.Get_PPM(MQ2Rs_R0)
	elif MQ2Rs_R0 <= 1.6 and MQ2Rs_R0 > 0.69:
		Gases[0] = 0
		Gases[1] = MQ2_CH4.Get_PPM(MQ2Rs_R0)
		Gases[2] = MQ2_Alch.Get_PPM(MQ2Rs_R0)
		Gases[3] = MQ2_H2.Get_PPM(MQ2Rs_R0)
		Gases[4] = MQ2_Prop.Get_PPM(MQ2Rs_R0)
		Gases[5] = MQ2_LPG.Get_PPM(MQ2Rs_R0)
	elif MQ2Rs_R0 <= 0.69 and MQ2Rs_R0 > 0.335:
		Gases[0] = 0
		Gases[1] = 0
		Gases[2] = 0
		Gases[3] = MQ2_H2.Get_PPM(MQ2Rs_R0)
		Gases[4] = MQ2_Prop.Get_PPM(MQ2Rs_R0)
		Gases[5] = MQ2_LPG.Get_PPM(MQ2Rs_R0)
	elif MQ2Rs_R0 <= 0.335 and MQ2Rs_R0 > 0.26:
		Gases[0] = 0
		Gases[1] = 0
		Gases[2] = 0
		Gases[3] = 0
		Gases[4] = MQ2_Prop.Get_PPM(MQ2Rs_R0)
		Gases[5] = MQ2_LPG.Get_PPM(MQ2Rs_R0)
	else:
		logger.debug("No MQ2PPM correction Done")

def Get_MQ7PPM(MQ7Rs_R0, Gases = []):
	"""
	This Function checks the RS/R0 value to select which gas is being detected
	"""
	if MQ7Rs_R0 <= 17 and MQ7Rs_R0 > 15:
		Gases[0] = MQ7_Alch.Get_PPM(MQ7Rs_R0)
		Gases[1] = 0
		Gases[2] = 0
		Gases[3] = 0
		Gases[4] = 0           
	elif MQ7Rs_R0 <=15 and MQ7Rs_R0 > 13:
		Gases[0] = MQ7_Alch.Get_PPM(MQ7Rs_R0)
		Gases[1] = MQ7_CH4.Get_PPM(MQ7Rs_R0)
		Gases[2] = 0
		Gases[3] = 0
		Gases[4] = 0
	elif MQ7Rs_R0 <=13 and MQ7Rs_R0 > 9:
		Gases[0] = 0
		Gases[1] = MQ7_CH4.Get_PPM(MQ7Rs_R0)
		Gases[2] = 0
		Gases[3] = 0
		Gases[4] = 0
	elif MQ7Rs_R0 <= 8.75 and MQ7Rs_R0 > 4.9:
		Gases[0] = 0
		Gases[1] = 0
		Gases[2] = MQ7_LPG.Get_PPM(MQ7Rs_R0)
		Gases[3] = 0
		Gases[4] = 0
	elif MQ7Rs_R0 <= 1.75 and MQ7Rs_R0 > 1.35:
		Gases[0] = 0
		Gases[1] = 0
		Gases[2] = 0
		Gases[3] = MQ7_CO.Get_PPM(MQ7Rs_R0)
		Gases[4] = 0
	elif MQ7Rs_R0 <= 1.35 and MQ7Rs_R0 > 0.092:
		Gases[0] = 0
		Gases[1] = 0
		Gases[2] = 0
		Gases[3] = MQ7_CO.Get_PPM(MQ7Rs_R0)
		Gases[4] = MQ7_H2.Get_PPM(MQ7Rs_R0)
	elif MQ7Rs_R0 <= 0.092 and MQ7Rs_R0 > 0.053:
		Gases[0] = 0
		Gases[1] = 0
		Gases[2] = 0
		Gases[3] = 0
		Gases[4] = MQ7_H2.Get_PPM(MQ7Rs_R0)

def Get_MQ135PPM(MQ135Rs_R0, Gases = []):
	"""
	This Function checks the RS/R0 value to select which gas is being detected
	"""           
	if MQ135Rs_R0 <= 2.85 and MQ135Rs_R0 > 2.59:
		Gases[0] = MQ135_CO.Get_PPM(MQ135Rs_R0)
		Gases[1] = 0
		Gases[2] = 0
		Gases[3] = 0
		Gases[4] = 0
		Gases[5] = 0
	elif MQ135Rs_R0 <=2.59 and MQ135Rs_R0 > 2.35:
		Gases[0] = MQ135_CO.Get_PPM(MQ135Rs_R0)
		Gases[1] = MQ135_NH4.Get_PPM(MQ135Rs_R0)
		Gases[2] = 0
		Gases[3] = 0
		Gases[4] = 0
		Gases[5] = 0
	elif MQ135Rs_R0 <=2.35 and MQ135Rs_R0 > 1.91:
		Gases[0] = MQ135_CO.Get_PPM(MQ135Rs_R0)
		Gases[1] = MQ135_NH4.Get_PPM(MQ135Rs_R0)
		Gases[2] = MQ135_CO2.Get_PPM(MQ135Rs_R0)
		Gases[3] = 0
		Gases[4] = 0
		Gases[5] = 0
	elif MQ135Rs_R0 <= 1.91 and MQ135Rs_R0 > 1.61:
		Gases[0] = MQ135_CO.Get_PPM(MQ135Rs_R0)
		Gases[1] = MQ135_NH4.Get_PPM(MQ135Rs_R0)
		Gases[2] = MQ135_CO2.Get_PPM(MQ135Rs_R0)
		Gases[3] = MQ135_Ethan.Get_PPM(MQ135Rs_R0)
		Gases[4] = 0
		Gases[5] = 0
	elif MQ135Rs_R0 <= 1.61 and MQ135Rs_R0 > 1.51:
		Gases[0] = MQ135_CO.Get_PPM(MQ135Rs_R0)
		Gases[1] = MQ135_NH4.Get_PPM(MQ135Rs_R0)
		Gases[2] = MQ135_CO2.Get_PPM(MQ135Rs_R0)
		Gases[3] = MQ135_Ethan.Get_PPM(MQ135Rs_R0)
		Gases[4] = MQ135_Methly.Get_PPM(MQ135Rs_R0)
		Gases[5] = 0
	elif MQ135Rs_R0 <= 1.51 and MQ135Rs_R0 > 1.44:
		Gases[0] = MQ135_CO.Get_PPM(MQ135Rs_R0)
		Gases[1] = MQ135_NH4.Get_PPM(MQ135Rs_R0)
		Gases[2] = MQ135_CO2.Get_PPM(MQ135Rs_R0)
		Gases[3] = MQ135_Ethan.Get_PPM(MQ135Rs_R0)
		Gases[4] = MQ135_Methly.Get_PPM(MQ135Rs_R0)
		Gases[5] = MQ135_Acet.Get_PPM(MQ135Rs_R0)
	elif MQ135Rs_R0 <= 1.44 and MQ135Rs_R0 > 0.8:
		Gases[0] = 0
		Gases[1] = MQ135_NH4.Get_PPM(MQ135Rs_R0)
		Gases[2] = MQ135_CO2.Get_PPM(MQ135Rs_R0)
		Gases[3] = MQ135_Ethan.Get_PPM(MQ135Rs_R0)
		Gases[4] = MQ135_Methly.Get_PPM(MQ135Rs_R0)
		Gases[5] = MQ135_Acet.Get_PPM(MQ135Rs_R0)           
	elif MQ135Rs_R0 <= 0.8 and MQ135Rs_R0 > 0.585:
		Gases[0] = 0
		Gases[1] = MQ135_NH4.Get_PPM(MQ135Rs_R0)
		Gases[2] = 0
		Gases[3] = MQ135_Ethan.Get_PPM(MQ135Rs_R0)
		Gases[4] = MQ135_Methly.Get_PPM(MQ135Rs_R0)
		Gases[5] = MQ135_Acet.Get_PPM(MQ135Rs_R0)

def main():
	init_logger()
	Reset()
	datafile = time.strftime('./Sensly_%d-%m-%Y_%H_%M_%S.csv')

	with open(datafile, 'w+') as f1:
		f1.write('Time, Carbon Monoxide PPM, Ammonia PPM, Carbon Dioxide PPM, Methly PPM, Acetone PPM, Methane PPM, LPG PPM, Hydrogen PPM, Propane PPM, PM10 \n')

	try:
		# Set commands for getting data from snesors 
		logger.info("Sensly is warming up please wait for %s seconds" % WARM_UP_TIMEOUT)
		sleep(WARM_UP_TIMEOUT)
		logger.info("Heating Completed")
		while True:
			log_data = []
			# Get current time and add data array
			log_data.append(time.strftime('%H:%M:%S'))

			# Reset the PPM value 
			COPPM = 0
			NH4PPM = 0
			CO2PPM = 0
			CO2H50HPPM = 0
			CH3PPM = 0
			CH3_2COPPM = 0
			AlchPPM = 0
			CH4PPM = 0
			LPGPPM = 0
			H2PPM = 0
			PropPPM = 0

			# Inialise the gases in an array 
			MQ2_Gases = [COPPM, CH4PPM, AlchPPM, H2PPM, PropPPM,LPGPPM]
			MQ7_Gases = [AlchPPM, CH4PPM, LPGPPM, COPPM, H2PPM]
			MQ135_Gases = [COPPM,NH4PPM,CO2PPM,CO2H50HPPM,CH3PPM,CH3_2COPPM]

			# Fetch the current temperatire and humidity
			temperature = temp_hum_sensor.read_temperature()
			logger.debug("Read temperature is %s" % temperature)
			humidity = temp_hum_sensor.read_humidity()
			logger.debug("Read humidity is %s" % humidity)

			# Correct the RS/R) ratio to account for temperature and humidity,
			# Then calculate the PPM for each gas
			#MQ2
			get_i2cdetect()
			MQ2Rs_R0 = MQ2.Corrected_RS_RO_MQ2( MQ2cmd, temperature, humidity, MQ2_t_30H, MQ2_t_60H, MQ2_t_85H)
			logger.debug("Getting MQ2 Sensor values")
			Get_MQ2PPM(MQ2Rs_R0, MQ2_Gases)
			
			#MQ7
			get_i2cdetect()
			MQ7Rs_R0 = MQ7.Corrected_RS_RO( MQ7cmd, temperature, humidity, MQ7_t_33H, MQ7_t_85H)
			logger.debug("Getting MQ7 Sensor values")
			Get_MQ7PPM(MQ7Rs_R0, MQ7_Gases)
			
			#MQ135
			get_i2cdetect()
			MQ135Rs_R0 = MQ135.Corrected_RS_RO( MQ135cmd, temperature, humidity, MQ135_t_33H, MQ135_t_85H)
			logger.debug("Getting MQ135 Sensor values")
			Get_MQ135PPM(MQ135Rs_R0, MQ135_Gases)
			
			# Store the calculated gases in an array
			log_data.append(MQ7_Gases[3])
			log_data.append(MQ135_Gases[1])
			log_data.append(MQ135_Gases[2])
			log_data.append(MQ135_Gases[4])
			log_data.append(MQ135_Gases[5])
			log_data.append(MQ2_Gases[1])
			log_data.append(MQ2_Gases[5])
			log_data.append(MQ2_Gases[3])
			log_data.append(MQ2_Gases[4])
			
			log_data.append(PM.Get_PMDensity(PMcmd))

			# Add the current array to the csv file 
			with open(datafile, 'a') as f2:
				logger.debug("Writting to file '%s' datas:%s" % (datafile, log_data))
				f2.write(','.join(str(d) for d in log_data) + '\n')
			    
			sleep(30)
	except KeyboardInterrupt:
		logger.info("Keyboard interruption")
	except Exception:
		logger.exception("Exception occured")
	finally:
		logger.info("Finally")



if __name__ == '__main__':
    main()   
	    
