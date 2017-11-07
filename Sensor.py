#Sensor Class
import Logging
from ABC import ABCMeta, abstractmethod, abstractproperty


class Sensor:
	__metaclass__ = ABCMeta

	#Class attributes
    	@abstractproperty
    	def resistance(self):
        	pass	

	def __init__(self):
		logging.basicConfig(stream=sys.stdout, level=logging.DEBUG, format='%(asctime)s.%(msecs)03d %(levelname)s %(module)s - %(funcName)s: %(message)s', datefmt="%Y-%m-%d %H:%M:%S")
		self.__init_sensors()

	
			
