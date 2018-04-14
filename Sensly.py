# ****************************************************************************************************
# Written by Sam Onwugbenu sam@altitude.pw founder of Altitude.tech
#
# 	Eddited by Philippe Gachoud ph.gachoud@gmail.com on 201711
#		For bug fixings and code commenting & readability
#
# For all values R0 is resistance in fresh air, Rs is sensor resistance in certain concentration of gas
#
# ****************************************************************************************************
import time 
import smbus 

import RPi.GPIO as GPIO
from Sensors import * 
import Adafruit_BME280
import logging
import sys
import os

SENSLY_WARMUP_TIME = 1 # Seconds to wait for warmup (AltitudeTech 600)
SAMPLING_SECONDS = 10 # Seconds to wait between data sampling (AltitudeTech 30)
DATA_FILE_NAME = './sampleData/Sensly_%d-%m-%Y_%H_%M_%S.csv' # File name where data are written, parentDir is created if not existing
DATA_FILE_HEADER = 'Time, Carbon Monoxide PPM, Ammonia PPM, Carbon Dioxide PPM, Methly PPM, Acetone PPM, Methane PPM, LPG PPM, Hydrogen PPM, Propane PPM, PM10'

# Sensly Constants 
R0 = [3120.5010, 1258.8822, 2786.3375]      # MQ2, MQ7, MQ135 R0 resistance (needed for PPM calculation).
                                            # Found by placing the Sensor in a clean air environment and running the calibration script
RSAir = [9.5,27,3.62]                       # Sensor RS/R0 ratio in clean air

LED = [0xFF, 0x00, 0x00]                    # Set LED to Red 

MQ2 = Sensor('MQ2',R0[0],RSAir[0])          # name, Calibrated R0 value, RSAir value 
MQ7 = Sensor('MQ7',R0[1],RSAir[1])
MQ135 = Sensor('MQ135',R0[2],RSAir[2])
opticalDustSensor = Sensor('PM',0,0)

# Set commands for getting data from sensors 
HAT_BUS_ADDRESS = 0x05
MQ2_INDEX = 0x01
MQ7_INDEX = 0x02
MQ135_INDEX = 0x03
DUST_SENSOR_INDEX = 0x04
BUS_WRITE_TIME_TO_SLEEP = 0.4


# Constants for temperature and humididty correction
MQ2_t_30H = [-0.00000072,0.00006753,-0.01530561,1.5594955]
MQ2_t_60H = [-0.00000012,0.00003077,-0.01287521,1.32473027]
MQ2_t_85H = [-0.00000033,0.00004116,-0.01135847,1.14576424]

MQ7_t_33H = [-0.00001017,0.00076638,-0.01894577,1.1637335]
MQ7_t_85H = [-0.00000481,0.0003916,-0.01267189,0.99930744]

MQ135_t_33H = [-0.00000042,0.00036988,-0.02723828,1.40020563]
MQ135_t_85H = [-0.0000002,0.00028254,-0.02388492,1.27309524]

# Gases constants
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

# Temperature, Humidity & barometric Pressure Sensor sensor declaration
bME280_Sensor = None 

# Initialises 
def initialize():
	logging.basicConfig(stream=sys.stdout, level=logging.DEBUG, format='%(asctime)s.%(msecs)03d %(levelname)s %(module)s - %(funcName)s: %(message)s', datefmt="%Y-%m-%d %H:%M:%S")
	ResetGPIO()

# Initializes BME Sensor
def init_BME280_Sensor():
	global bME280_Sensor
	logging.debug("----- BME Sensor {}")
	bME280_Sensor = Adafruit_BME280.BME280(t_mode=Adafruit_BME280.BME280_OSAMPLE_8, h_mode=Adafruit_BME280.BME280_OSAMPLE_8, address=0x76) # Sometimes Crash with a connection timeout

# Reseting the HAT
def ResetGPIO():
    GPIO.setmode(GPIO.BCM) ## Use BCM numbering
    GPIO.setup(23, GPIO.OUT)
    # Reset Sensly HAT
    GPIO.output(23, False) ## Set GPIO Pin 23 to low
    time.sleep(0.8)
    GPIO.output(23, True) ## Set GPIO Pin 23 to low
    time.sleep(0.5)
    # Clean up the GPIO pins 
#    GPIO.cleanup() # unusefull


  
def Get_MQ2PPM(MQ2Rs_R0, Gases = []):
    """This Function checks the RS/R0 value to select which gas is being detected"""
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
      	logging.debug("No value has been changed into MQ2PPM")

def Get_MQ7PPM(MQ7Rs_R0, Gases = []):
    """This Function checks the RS/R0 value to select which gas is being detected"""
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
    else:
        logging.debug("No value has been changed into MQ7PPM")

def Get_MQ135PPM(MQ135Rs_R0, Gases = []):
    """This Function checks the RS/R0 value to select which gas is being detected"""
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
    else:
	logging.debug("No value has been changed into MQ135PPM")
        
        
def save_read_data_to_csv():
	"""Writes read data from sensors into csv files"""
	global COPPM, NH4, CO2PPM, CO2H50HPPM, CH3PPM, CH3_2COPPM, AlchPPM, CH4PPM, LPGPPM, H2PPM, PropPPM 

	#Warmum otherwise data are not the same, seems that after 10 minutes the data become more stables
	logging.info("Sensly is warming up please wait for " + str(SENSLY_WARMUP_TIME) + " seconds")
	time.sleep(SENSLY_WARMUP_TIME)
	logging.info("Warmup completed")
	#CSV File header
	datafile = time.strftime(DATA_FILE_NAME)
	directory = os.path.dirname(DATA_FILE_NAME)
	if not os.path.exists(directory):
		os.makedirs(directory)
	logging.debug("Writting header to " + str(datafile))
	with open(datafile, 'w+') as f1:
		f1.write(DATA_FILE_HEADER + '\n')

	try:
		logging.info("Enterring to a True loop, Ctrl+c to stop it...")
		while True:
			data = []
			# Get current time and add data array
			data.append(time.strftime('%H:%M:%S'))

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
			MQ2_Gases = [COPPM, CH4PPM, AlchPPM, H2PPM, PropPPM, LPGPPM]
			MQ7_Gases = [AlchPPM, CH4PPM, LPGPPM, COPPM, H2PPM]
			MQ135_Gases = [COPPM, NH4PPM, CO2PPM, CO2H50HPPM, CH3PPM, CH3_2COPPM]

			# Fetch the current temperature and humidity
			temperature = bME280_Sensor.read_temperature()
			logging.debug("BME280 read temperature is (Carefull, hat is hot so temp is not corrected by default):" + str(temperature))
			
			logging.debug("BME280 read humidity is (Carefull, hat is hot so temp is not corrected by default):" + str(humidity))

			# Correct the RS/R0 ratio to account for temperature and humidity,
			# Then calculate the PPM for each gas
			MQ2Rs_R0 = MQ2.Corrected_RS_RO_MQ2( MQ2_INDEX, temperature, humidity, MQ2_t_30H, MQ2_t_60H, MQ2_t_85H)
			Get_MQ2PPM(MQ2Rs_R0, MQ2_Gases)

			ResetGPIO() 
			MQ7Rs_R0 = MQ7.Corrected_RS_RO( MQ7_INDEX, temperature, humidity, MQ7_t_33H, MQ7_t_85H)
			Get_MQ7PPM(MQ7Rs_R0, MQ7_Gases)

			ResetGPIO() 
			MQ135Rs_R0 = MQ135.Corrected_RS_RO( MQ135_INDEX, temperature, humidity, MQ135_t_33H, MQ135_t_85H)
			Get_MQ135PPM(MQ135Rs_R0, MQ135_Gases)

			logging.debug("Gases are followings MQ2 {}\n MQ7 {}\n MQ135 {}\n".format(MQ2_Gases, MQ7_Gases, MQ135_Gases))
			# Store the calculated gases in an array
			data.append(MQ7_Gases[3])
			data.append(MQ135_Gases[1])
			data.append(MQ135_Gases[2])
			data.append(MQ135_Gases[4])
			data.append(MQ135_Gases[5])
			data.append(MQ2_Gases[1])
			data.append(MQ2_Gases[5])
			data.append(MQ2_Gases[3])
			data.append(MQ2_Gases[4])

			# Getting informations from optical Dust Sensor
			ResetGPIO() 
			logging.debug("Getting informations from Optical Dust Sensor")
			pmData = opticalDustSensor.Get_PMDensity(Sensor.OPTICAL_DUST_SENSOR_CMD)
			data.append(pmData)

			# Add the current array to the csv file 
			with open(datafile, 'a') as f2:
				toWrite = ','.join(str(d) for d in data) + '\n'
				f2.write(toWrite)
				logging.debug("Writting to datafile:" + toWrite + " " + DATA_FILE_HEADER) 

			logging.debug("-------- Waiting for another " + str(SAMPLING_SECONDS) + " seconds till next data getting")
			time.sleep(SAMPLING_SECONDS)
	except KeyboardInterrupt:
		logging.info("You pressed Ctrl+C, Bye")
	finally:
		logging.info("You can check your data into " + DATA_FILE_NAME) 
		GPIO.cleanup() #resets any ports you have used in this program back to input mode


# Write I2C block (from https://github.com/DexterInd/GrovePi/blob/master/Software/Python/grovepi.py)
def write_i2c_block(address, block):
	bus = smbus.SMBus(1)
	RETRIES = 10
	result = -1
        for i in range(RETRIES):
                try:
                        result = bus.write_i2c_block_data(address, 1, block)
			logging.debug("Writting i2c block succeeded after " + str(i) + " times")
			break
                except IOError:
			logging.debug("IO Error trying to write block data to " + str(address) + " block:" + str(block) + " " + str(i) + " times")
        return result 


def dust_sensor_read_test_v1():
	"""Testing dustsensor raw commands"""
	# I2C Address of Arduino
	address = 0x05
	dust_sensor_en_cmd=[14]
	dust_sensor_dis_cmd=[15]
	dus_sensor_read_cmd=[10]
	unused = 0 ## This allows us to be more specific about which commands contain unused bytes
	bus = smbus.SMBus(1)
	#init or en
	write_i2c_block(address, dust_sensor_en_cmd + [unused, unused, unused])
	time.sleep(.2)
	#dis
	write_i2c_block(address, dust_sensor_dis_cmd + [unused, unused, unused])
	time.sleep(.2)
	#read
        write_i2c_block(address, dus_sensor_read_cmd + [unused, unused, unused])
        time.sleep(.2)
        #read_i2c_byte(address)
        #number = read_i2c_block(address)
        #return (number[1] * 256 + number[2])
        data_back= bus.read_i2c_block_data(address, 1)[0:4]
        #print data_back[:4]
        if data_back[0]!=255:
                lowpulseoccupancy=(data_back[3]*256*256+data_back[2]*256+data_back[1])
                logging.debug(str([data_back[0],lowpulseoccupancy]))
                return [data_back[0],lowpulseoccupancy]
        else:
                return [-1,-1]
        print (data_back)


"""Writes the given sensorIndex on the HAT
	This selects the sensor you'll get the informations from doing a read_byte after this method
"""
def select_sensor(sensorIndex):
	bus.write_byte(HAT_BUS_ADDRESS, sensorIndex)
	time.sleep(BUS_WRITE_TIME_TO_SLEEP)

""" Reads a byte on HAT_BUS_ADDRESS
	If an IOError occures, will try 'retriesCount' times before getting out of the loop and returning -1
	Between two read it'll wait 'waitTimeBetweenTwoRead'
"""
def get_read_byte(retriesCount, waitTimeBetweenTwoRead):
	result = -1
	for i in range(retriesCount):
		try:
			result = bus.read_byte(HAT_BUS_ADDRESS)
			time.sleep(waitTimeBetweenTwoRead)
			logging.debug("Read gave result '{}' after '{}' times".format(result, i))
			break
		except IOError:
			logging.warn("IO Error trying to read byte on HAT after '{}'times".format(i))
		except:
			logging.error("Unexpected error:", sys.exc_info()[0])
			raise

	return result	


""" Reads infos from dust sensor"""
def dust_sensor_read_test_v2():
	global bus

	logging.info("---- DUST SenSoR ----")
	bus = smbus.SMBus(1)
	waitTimeToRead = 0.3
	waitTimeWrite = 0.4
	retriesCount = 10
	select_sensor(DUST_SENSOR_INDEX)
	get_read_byte(retriesCount, waitTimeToRead)
	get_read_byte(retriesCount, waitTimeToRead)

""" Reads infos from MQ2"""
def MQ2_test():
	global bus
	logging.info("---- MQ2 ----")
	bus = smbus.SMBus(1)
	waitTimeToRead = 0.3
	waitTimeWrite = 0.4
	retriesCount = 10
	select_sensor(MQ2_INDEX)
	b1 = get_read_byte(retriesCount, waitTimeToRead)
	b2 = get_read_byte(retriesCount, waitTimeToRead)
	val = b1<<8|b2
	logging.debug("======> MQ2 Sensor raw value is %s" % val)


""" Reads infos from MQ7"""
def MQ7_test():
	global bus
	logging.info("---- MQ7 ----")
	bus = smbus.SMBus(1)
	waitTimeToRead = 0.3
	waitTimeWrite = 0.4
	retriesCount = 10
	select_sensor(MQ7_INDEX)
	b1 = get_read_byte(retriesCount, waitTimeToRead)
	b2 = get_read_byte(retriesCount, waitTimeToRead)
	val = b1<<8|b2
	logging.debug("======> MQ7 Sensor raw value is %s" % val)


""" Reads infos from MQ135"""
def MQ135_test():
	global bus
	logging.info("---- MQ135 ----")
	bus = smbus.SMBus(1)
	waitTimeToRead = 0.3
	waitTimeWrite = 0.4
	retriesCount = 10
	select_sensor(MQ135_INDEX)
	b1 = get_read_byte(retriesCount, waitTimeToRead)
	b2 = get_read_byte(retriesCount, waitTimeToRead)
	val = b1<<8|b2
	logging.debug("======> MQ135 Sensor raw value is %s" % val)

def LED_test():
	MQ2_H2.Set_LED(Green)

# *******************************************
# MAIN FUNCTION
# *******************************************
try:
	# Initialize
	initialize()
	init_BME280_Sensor()
	#dust_sensor_read_test_v1()
	dust_sensor_read_test_v2()
	MQ2_test()
	MQ7_test()
	MQ135_test()
	#LED_test()
	# All sensors tested
	save_read_data_to_csv()
except KeyboardInterrupt:
	logging.info("You pressed Ctrl+C, Bye")
finally:
	logging.info("You can check your data into " + DATA_FILE_NAME) 
	GPIO.cleanup() #resets any ports you have used in this program back to input mode

 
