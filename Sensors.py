# Module that contains the functions necessary for the operation
# of the Sensly HAT

# Import common modules needed for script
import sys
import time
from math import log10
import logging


import smbus as I2C # Import installed modules need for script

# Define the i2c address for the Sensly HAT
I2C_HAT_ADDRESS = 0x05

# LED Constants
# Array containing RGB values for LED [RED Brightness, Green Brightness, Blue Brightness]
Green = [0x00,0x00,0xFF] 
Orange = [0xFF,0x09,0x00]
Off = [0x00,0x00,0x00]

# i2c cmd to set LED value
LEDcmd = 0x07 

# MQ Constants for interpreting raw sensor data
MaxADC = 4095
RLOAD = 10000

# PM Constants for interpreting raw PM data
NODUSTVOLTAGE = 500
COVRATIO = 0.2


#******************** SENSOR CLASS *************************************************
class Sensor:

	#variables
	__logger = None
	RS = 0 # Resistance

	def __init__(self, name, R0, RSAIR):
		self.name = name
		i2c = I2C.SMBus(1)  
		self._device = i2c
		self.R0 = R0
		self.RLOAD = RLOAD
		self.RSAIR = RSAIR
		self.MaxADC = MaxADC

		logging.basicConfig(stream=sys.stdout, level=logging.DEBUG, format='%(asctime)s.%(msecs)03d %(levelname)s %(module)s - %(funcName)s: %(message)s', datefmt="%Y-%m-%d %H:%M:%S")
		self.__logger = logging.getLogger(__name__)

	def Get_rawdata(self,cmd):
		"""
		Function to get raw data for the sensors from the Sensly HAT via the i2c peripheral
			Reads 2 bytes after setting mode with write byte cmd, sets self.Raw to it, and returns self.Raw
		"""
		data = []
		self.__logger.debug("Writting byte %s to address %s (selecting sensor)" % (I2C_HAT_ADDRESS, cmd))
		self._device.write_byte(I2C_HAT_ADDRESS,cmd) # Crashes here with 121 remote IO Error (Selecting sensor)
		time.sleep(0.01) # Original from altitude
		#Byte 1
		read_byte = self._device.read_byte(I2C_HAT_ADDRESS)
		self.__logger.debug("Read byte is %s" % read_byte)
		data.append(read_byte)
		time.sleep(0.01)
		#Byte 2
		read_byte = self._device.read_byte(I2C_HAT_ADDRESS)
		self.__logger.debug("Read byte is %s" % read_byte)
		data.append(read_byte)

		self.Raw = data[0] 
		self.Raw = (self.Raw<<8) | data[1]
		self.__logger.debug("Self.Raw is now %s" % self.Raw)
		return self.Raw

	def Get_RS(self,cmd):
		"""
		# Function to convert the raw data to a resistance value 
		"""
		self.RS = ((float(self.MaxADC)/float(self.Get_rawdata(cmd))-1)*self.RLOAD)
		self.__logger.debug("Resistance value of raw data is %s" % self.RS)
		return self.RS

	def Get_RSR0Ratio(self,cmd):
		"""
		# Function to calculate the RS(Sensor Resistance)/R0(Base Resistance) ratio    
		"""
		self.rsro = float(self.Get_RS(cmd)/self.R0)
		return self.rsro

	def Calibrate(self, cmd, Cal_Sample_Time):
		"""
		# Experimental function to calibrate the MQ Sensors
		"""
		AvRs = 0
		for x in range(Cal_Sample_Time):
			AvRs = AvRs + self.Get_RS(cmd)
			time.sleep(1)
		AvRs = AvRs/Cal_Sample_Time
		self.RZERO = AvRs/RSAIR
		return self.RZERO

	# 
	def Get_PMVolt(self, cmd):
		"""Function to calculate the voltage from raw PM data"""
		self.PMVolt = ((3300.00/self.MaxADC)*float(self.Get_rawdata(cmd))*11.00)
		return self.PMVolt

	def Get_PMDensity(self, cmd):
		"""
		Function to calculate the densisty of the particulate matter detected 
		"""
		self.Get_PMVolt(cmd)
		if (self.PMVolt >= NODUSTVOLTAGE):
		    self.PMVolt -= NODUSTVOLTAGE
		    self.PMDensity = self.PMVolt * COVRATIO
		else:
			    self.PMDensity = 0            
		return self.PMDensity

	# 
	def Corrected_RS_RO(self, cmd, temperature, humidity, Const_33 = [], Const_85 = []):
		"""
		Function to correct the RS/R0 ratio based on temperature and relative humidity
		"""
		rsro_ambtemp_33RH = (Const_33[0]*pow(temperature,3)) + (Const_33[1]*pow(temperature,2)) + (Const_33[2]*temperature) + Const_33[3]
		rsro_ambtemp_85RH = (Const_85[0]*pow(temperature,3)) + (Const_85[1]*pow(temperature,2)) + (Const_85[2]*temperature) + Const_85[3]
		rsro_ambtemp_65RH = ((65.0-33.0)/(85.0-65.0)*(rsro_ambtemp_85RH-rsro_ambtemp_33RH)+rsro_ambtemp_33RH)*1.102
		if humidity < 65:
		    rsro_ambtemp_ambRH = (humidity-33)/(65-33)*(rsro_ambtemp_65RH-rsro_ambtemp_33RH)+rsro_ambtemp_33RH
		else:
		    rsro_ambtemp_ambRH = (humidity-65)/(85-65)*(rsro_ambtemp_85RH-rsro_ambtemp_65RH)+rsro_ambtemp_65RH
		#calculate correction factor
		refrsro_at_20C65RH = 1.00
		rsroCorrPct = 1 + (refrsro_at_20C65RH - rsro_ambtemp_ambRH)/ refrsro_at_20C65RH
		correctedrsro = rsroCorrPct * (self.Get_RSR0Ratio(cmd))
		return correctedrsro

	def Corrected_RS_RO_MQ2(self, cmd, temperature, humidity, Const_30 = [], Const_60 = [], Const_85 = []):
		"""
		Function to correct the RS/R0 ratio based on temperature and relative humidity for the MQ2
		"""
		rsro_ambtemp_30RH = (Const_30[0]*pow(temperature,3)) + (Const_30[1]*pow(temperature,2)) + (Const_30[2]*temperature) + Const_30[3]
		rsro_ambtemp_60RH = (Const_60[0]*pow(temperature,3)) + (Const_60[1]*pow(temperature,2)) + (Const_60[2]*temperature) + Const_60[3]
		rsro_ambtemp_85RH = (Const_85[0]*pow(temperature,3)) + (Const_85[1]*pow(temperature,2)) + (Const_85[2]*temperature) + Const_85[3]

		if humidity < 60:
			rsro_ambtemp_ambRH = (humidity-30)/(60-30)*(rsro_ambtemp_60RH-rsro_ambtemp_30RH)+rsro_ambtemp_30RH
		else:
			rsro_ambtemp_ambRH = (humidity-60)/(85-60)*(rsro_ambtemp_85RH-rsro_ambtemp_60RH)+rsro_ambtemp_60RH
		# Calculate correction factor
		refrsro_at_20C60RH = 1.00
		rsroCorrPct = 1 + (refrsro_at_20C60RH - rsro_ambtemp_ambRH)/ refrsro_at_20C60RH
		correctedrsro = rsroCorrPct * (self.Get_RSR0Ratio(cmd))
		return correctedrsro

#******************** GAS CLASS *************************************************
class Gas:
    
	def __init__(self,name,rsromax,rsromin,gradient,intercept, threshold, LED = []):
		self.name = name
		i2c = I2C.SMBus(1)  
		self._device = i2c
		self.min = rsromin
		self.max = rsromax
		self.gradient = gradient
		self.intercept = intercept
		self.threshold = threshold
		self.LED = LED
		LEDcmd = 0x07

		logging.basicConfig(stream=sys.stdout, level=logging.DEBUG, format='%(asctime)s.%(msecs)03d %(levelname)s %(module)s - %(funcName)s: %(message)s', datefmt="%Y-%m-%d %H:%M:%S")
	

	def Get_PPM(self, rs_ro):
		"""
		Sets self.PPM and returns it
		"""
		self.PPM = pow(10,((self.gradient*(log10(rs_ro)))+self.intercept))
		self.__logger.debug("Received_PPM is %s" % self.PPM)
		return self.PPM

	def Set_LED(self, LEDColour):  # LEDColour = Red , Green, Blue Brightness values from 0 - 255 in an array   
		"""
		Function to set the LED Color, used for setting alarms points
		"""
		self._device.write_byte(I2C_HAT_ADDRESS,LEDcmd)
		self.__logger.debug("Setting LEd color to %s" % LEDColour)
		for x in range(3):
			self._device.write_byte(I2C_HAT_ADDRESS,self.LEDColour[x])
	    
	# Function to check the PPM value against the predefined threshold         
	def Chk_threshold(self):
		self.__logger.debug("Checking threshold for LED setting")
		if self.PPM < self.threshold:
			self.Set_LED(Green)
		elif self.PPM == self.threshold:
			self.Set_LED(Orange)
		elif self.PPM > self.threshold: # Correctme: if neither equal or less than bigger wrong??
			self.Set_LED(self.LED)
