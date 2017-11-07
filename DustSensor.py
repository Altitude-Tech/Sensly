# DustSensor actually Sharp GP2Y10
class DustSensor(Sensor):
	
	#Attributes
	PPM = None
    
    def __init__(self, name, rsromax, rsromin, gradient, intercept, threshold, LED = []):
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

    def get_PPM(self, rs_ro):
	"""Function to calculate the PPM of the specific gas"""
        self.PPM = pow(10,((self.gradient*(log10(rs_ro)))+self.intercept))
        return self.PPM
    
    def set_LED(self, LEDColour):  
    	""" Function to set the LED Color, used for setting alarms points
		LEDColour = Red , Green, Blue Brightness values from 0 - 255 in an array  """ 
        self._device.write_byte(I2C_Addr,LEDcmd)
        for x in range(3):
            self._device.write_byte(I2C_Addr,self.LEDColour[x])
            
    def chk_threshold(self):
	"""Function to check the PPM value against the predefined threshold""" 
        if self.PPM < self.threshold:
            self.set_LED(Green)
        elif self.PPM == self.threshold:
            self.set_LED(Orange)
        elif self.PPM > self.threshold:
            self.set_LED(self.LED)


