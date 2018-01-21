# Hat Object
import logging

Class SenslyHat:
	#Constants
	MQ2_LOAD_RESISTANCE = 9.5
	MQ7_LOAD_RESISTANCE = 27
	MQ135_LOAD_RESISTANCE = 3.62 

	#Class attributes
	mq2Sensor = None
	mq7Sensor = None
	mq135Sensor = None

	def __init__(self):
		logging.basicConfig(stream=sys.stdout, level=logging.DEBUG, format='%(asctime)s.%(msecs)03d %(levelname)s %(module)s - %(funcName)s: %(message)s', datefmt="%Y-%m-%d %H:%M:%S")
		self.__init_sensors()

	def __initSensors():
		"""Initalizes sensors"""
		mq2Sensor = Sensor('MQ2', 0, MQ2_LOAD_RESISTANCE)
		mq7Sensor = Sensor('MQ7', 0, MQ7_LOAD_RESISTANCE)
		mq135Sensor = Sensor('MQ135', 0, MQ135_LOAD_RESISTANCE)
			
