#MQ Sensor Class
class MQSensor(Sensor):

	#Class attributes
	resistance = # Found by placing the Sensor in a clean air environment and running the calibration script
	rSAir# Sensor RS/R0 ratio in clean air
	LOAD_RESISTANCE = None
	r0 = None
	rLOAD = None
	rAir = None
	maxADC = None
	raw = None

	_device = None
	
    def __init__(self, name, R0, RSAIR):
        self.name = name
        i2c = I2C.SMBus(1)  
        self._device = i2c
        self.R0 = R0
        self.RLOAD = RLOAD
        self.RSAIR = RSAIR
        self.MaxADC = MaxADC
        
    def get_rawdata(self, cmd):
	"""Function to get raw data for the sensors from the Sensly HAT via the i2c peripheral"""
        data = []
        self._device.write_byte(I2C_Addr,cmd)
        time.sleep(0.01)
        data.append(self._device.read_byte(I2C_Addr))
        time.sleep(0.01)
        data.append(self._device.read_byte(I2C_Addr))

        self.raw = data[0] 
        self.raw = (self.raw<<8) | data[1]
        return self.raw
    
    def get_RS(self,cmd):
	"""Function to convert the raw data to a resistance value""" 
        self.RS = ((float(self.MaxADC)/float(self.get_rawdata(cmd))-1)*self.RLOAD)
        return self.RS
    
    def get_RSR0Ratio(self,cmd):
	"""Function to calculate the RS(Sensor Resistance)/R0(Base Resistance) ratio"""    
        self.rsro = float(self.get_RS(cmd)/self.R0)
        return self.rsro
    
    def calibrate(self, cmd, cal_Sample_Time):
	"""Experimental function to calibrate the MQ Sensors"""
        AvRs = 0
        for x in range(cal_Sample_Time):
            AvRs = AvRs + self.get_RS(cmd)
            time.sleep(1)
        AvRs = AvRs/cal_Sample_Time
        self.RZERO = AvRs/RSAIR
        return self.RZERO
    
    def get_PMVolt(self, cmd):
	"""Function to calculate the voltage from raw PM data"""
        self.PMVolt = ((3300.00/self.MaxADC)*float(self.get_rawdata(cmd))*11.00)
        return self.PMVolt
    
    def get_PMDensity(self, cmd):
	"""Function to calculate the densisty of the particulate matter detected""" 	
        self.get_PMVolt(cmd)
        if (self.PMVolt >= NODUSTVOLTAGE):
            self.PMVolt -= NODUSTVOLTAGE
            self.PMDensity = self.PMVolt * COVRATIO
        else:
            self.PMDensity = 0            
        return self.PMDensity
    
    def Corrected_RS_RO(self, cmd, temperature, humidity, Const_33 = [], Const_85 = []):
	"""Function to correct the RS/R0 ratio based on temperature and relative humidity"""
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
        correctedrsro = rsroCorrPct * (self.get_RSR0Ratio(cmd))
        return correctedrsro
    
    def Corrected_RS_RO_MQ2(self, cmd, temperature, humidity, Const_30 = [], Const_60 = [], Const_85 = []):
	"""Function to correct the RS/R0 ratio based on temperature and relative humidity for the MQ2"""
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
        correctedrsro = rsroCorrPct * (self.get_RSR0Ratio(cmd))
        return correctedrsro
 
