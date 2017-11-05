from time import *

import RPi.GPIO as GPIO
from Sensors import Sensor, Gas
from bme_combo import *
import logging
import sys

logging.basicConfig(stream=sys.stdout, level=logging.DEBUG, format='%(asctime)s.%(msecs)03d %(levelname)s %(module)s - %(funcName)s: %(message)s', datefmt="%Y-%m-%d %H:%M:%S")
logging.debug("start of script")
logging.debug("debug test this is logged as debug level")

def my_init():
	# Set up GPIO ports
	GPIO.setmode(GPIO.BCM)      # Use BCM numbering
	GPIO.setup(23, GPIO.OUT)
	# Reset Sensly HAT
	GPIO.output(23, False)      # Set GPIO Pin 4 to low
	#GPIO.output(25, True)      # Set GPIO Pin 4 to low
	time.sleep(1)
	GPIO.output(23, True)       # Set GPIO Pin 4 to low
	# Clean up GPIO 
	GPIO.cleanup()

def my_small_init():
	GPIO.setmode(GPIO.BCM)      # Use BCM numbering
	GPIO.setup(23, GPIO.OUT)
	# Reset Sensly HAT
	GPIO.output(23, False)      # Set GPIO Pin 4 to low
	#GPIO.output(25, True)      # Set GPIO Pin 4 to low
	time.sleep(1)
	GPIO.output(23, True)       # Set GPIO Pin 4 to low
	time.sleep(1)
	time.sleep(1)

# Sensly Constants 
R0 = [0,0,0]
RSAir = [9.5,27,3.62]
RLOAD = 10000               # In Ohms
Cal_Sample_Time = 5


MQ2 = Sensor('MQ2',R0[0],RSAir[0]) # name, max adc value, Calibrated R0 value, load resistance
MQ7 = Sensor('MQ7',R0[1],RSAir[1])
MQ135 = Sensor('MQ135',R0[2],RSAir[2])
ADCMax = 4095

my_init()

datafile = time.strftime('./Sensly_Calibration_%d-%m-%Y_%H_%M_%S.csv')

logging.debug("Before file open")
with open(datafile, 'w+') as f1:
    f1.write('Time, MQ2RZero, MQ7RZero, MQ135RZero\n')
try:
    # Set commands for getting data from snesors 
    MQ2cmd = 0x01
    MQ7cmd = 0x02
    MQ135cmd = 0x03
    # Initialise the last stored R0 value used for the running average
    L_AvRs_MQ2 = 0
    L_AvRs_MQ7 = 0
    L_AvRs_MQ135 = 0
    logging.warn("Before sleep")
    sleep(1)
    while True:
        logging.debug("Entering loop While True")
        data = []
        # Get current time and add data array
        data.append(time.strftime('%H:%M:%S'))

        # Initalise Average resistance values 
        AvRs_MQ2 = 0
        AvRs_MQ7 = 0
        AvRs_MQ135 = 0

        logging.debug("Starting calibration")
        # Run calibration   
        for x in range(Cal_Sample_Time):
	    my_small_init()
            AvRs_MQ2 = AvRs_MQ2 + MQ2.Get_RS(MQ2cmd)
            logging.debug("--------- Got first data AvRs_MQ2:"+str(AvRs_MQ2))
            sleep(0.01)
	    my_small_init()
	    logging.debug("--------- Trying to get Data from MQ7")
            AvRs_MQ7 = AvRs_MQ7 + MQ7.Get_RS(MQ7cmd)
            logging.debug("--------- Got data AvRs_MQ7:"+str(AvRs_MQ7))
            sleep(0.01)
	    my_small_init()
	    logging.debug("--------- Trying to get Data from MQ135")
            AvRs_MQ135 = AvRs_MQ135 + MQ135.Get_RS(MQ135cmd)
            logging.debug("--------- Got data MQ135:"+str(AvRs_MQ135))
            sleep(0.01)
	    logging.debug("*********************** ENDING LOOP *********")
        AvRs_MQ2 = AvRs_MQ2/Cal_Sample_Time
        AvRs_MQ7 = AvRs_MQ7/Cal_Sample_Time
        AvRs_MQ135 = AvRs_MQ135/Cal_Sample_Time

        # Find R0
        MQ2.R0 = ((AvRs_MQ2/MQ2.RSAIR) + L_AvRs_MQ2)/2
        MQ7.R0 = ((AvRs_MQ7/MQ7.RSAIR) + L_AvRs_MQ7)/2
        MQ135.R0 = ((AvRs_MQ135/MQ135.RSAIR) + L_AvRs_MQ135)/2

        L_AvRs_MQ2 =  MQ2.R0
        L_AvRs_MQ7 = MQ7.R0
        L_AvRs_MQ135 = MQ135.R0           

        # Store the values in a file
        data.append(MQ2.R0)
        data.append(MQ7.R0)
        data.append(MQ135.R0)

        with open(datafile, 'a') as f2:
            f2.write(','.join(str(d) for d in data) + '\n')
        
except KeyboardInterrupt:
    GPIO.cleanup()
    print "Bye"
