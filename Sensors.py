# Module that contains the functions necessary for the operation
# of the Sensly HAT.
#
# Python 3 port. Works on Raspberry Pi 4 (and other models) running
# Raspberry Pi OS Bookworm or later.

import sys
import time
from math import log10

# I2C access: prefer smbus2 (pip / apt python3-smbus2), fall back to the
# classic python3-smbus package. Both expose the same SMBus API.
try:
    from smbus2 import SMBus
except ImportError:  # pragma: no cover - depends on installed packages
    try:
        from smbus import SMBus
    except ImportError:
        sys.exit(
            "No I2C library found. Install one with:\n"
            "  sudo apt install python3-smbus2\n"
            "or\n"
            "  sudo apt install python3-smbus"
        )

# I2C bus number. Bus 1 is the GPIO header I2C bus on every Pi since the
# model B rev 2 (including the Pi 4).
I2C_BUS = 1

# Define the i2c address for the Sensly HAT
I2C_Addr = 0x05

# GPIO (BCM numbering) connected to the Sensly HAT reset line
RESET_PIN = 23

# LED Constants
# Array containing RGB values for LED [RED Brightness, Green Brightness, Blue Brightness]
Green = [0x00, 0x00, 0xFF]
Orange = [0xFF, 0x09, 0x00]
Off = [0x00, 0x00, 0x00]

# i2c cmd to set LED value
LEDcmd = 0x07

# MQ Constants for interpreting raw sensor data
MaxADC = 4095
RLOAD = 10000

# PM Constants for interpreting raw PM data
NODUSTVOLTAGE = 500
COVRATIO = 0.2

# Number of times an I2C transfer is retried before giving up
I2C_RETRIES = 3

# A single shared bus handle for every sensor object
_bus = None


def get_bus():
    """Return the shared SMBus handle, opening it on first use."""
    global _bus
    if _bus is None:
        try:
            _bus = SMBus(I2C_BUS)
        except (FileNotFoundError, PermissionError) as exc:
            sys.exit(
                "Could not open /dev/i2c-%d (%s).\n"
                "Enable I2C with 'sudo raspi-config' -> Interface Options -> I2C\n"
                "(or run: sudo raspi-config nonint do_i2c 0) and reboot."
                % (I2C_BUS, exc)
            )
    return _bus


def reset_hat(low_time=0.5):
    """Pulse the Sensly HAT reset line (GPIO 23) low then high.

    Uses gpiozero (the supported GPIO library on current Raspberry Pi OS)
    and falls back to RPi.GPIO on older images.
    """
    try:
        from gpiozero import OutputDevice

        reset = OutputDevice(RESET_PIN, active_high=True, initial_value=True)
        reset.off()
        time.sleep(low_time)
        reset.on()
        reset.close()
        return
    except ImportError:
        pass

    try:
        import RPi.GPIO as GPIO
    except ImportError:
        sys.exit(
            "No GPIO library found. Install one with:\n"
            "  sudo apt install python3-gpiozero"
        )
    GPIO.setmode(GPIO.BCM)
    GPIO.setup(RESET_PIN, GPIO.OUT)
    GPIO.output(RESET_PIN, False)
    time.sleep(low_time)
    GPIO.output(RESET_PIN, True)
    GPIO.cleanup()


class Sensor:

    def __init__(self, name, R0, RSAIR):
        self.name = name
        self._device = get_bus()
        self.R0 = R0
        self.RLOAD = RLOAD
        self.RSAIR = RSAIR
        self.MaxADC = MaxADC
        self.Raw = 0
        self.RS = 0.0
        self.rsro = 0.0
        self.PMVolt = 0.0
        self.PMDensity = 0.0

    # Function to get raw data for the sensors from the Sensly HAT via the i2c peripheral
    def Get_rawdata(self, cmd):
        last_error = None
        for _ in range(I2C_RETRIES):
            try:
                self._device.write_byte(I2C_Addr, cmd)
                time.sleep(0.01)
                high = self._device.read_byte(I2C_Addr)
                time.sleep(0.01)
                low = self._device.read_byte(I2C_Addr)
                self.Raw = (high << 8) | low
                return self.Raw
            except OSError as exc:
                last_error = exc
                time.sleep(0.05)
        raise OSError(
            "I2C read from Sensly HAT (address 0x%02X, cmd 0x%02X) failed: %s\n"
            "Check the HAT is seated and that 'i2cdetect -y 1' shows 05 and 76."
            % (I2C_Addr, cmd, last_error)
        )

    # Function to convert the raw data to a resistance value
    def Get_RS(self, cmd):
        raw = self.Get_rawdata(cmd)
        if raw <= 0:
            # Sensor is reading zero volts (not warmed up / disconnected);
            # treat as effectively infinite resistance rather than crashing.
            self.RS = float('inf')
        else:
            self.RS = ((float(self.MaxADC) / float(raw)) - 1) * self.RLOAD
        return self.RS

    # Function to calculate the RS(Sensor Resistance)/R0(Base Resistance) ratio
    def Get_RSR0Ratio(self, cmd):
        self.rsro = float(self.Get_RS(cmd) / self.R0)
        return self.rsro

    # Experimental function to calibrate the MQ Sensors
    def Calibrate(self, cmd, Cal_Sample_Time):
        AvRs = 0
        for _ in range(Cal_Sample_Time):
            AvRs = AvRs + self.Get_RS(cmd)
            time.sleep(1)
        AvRs = AvRs / Cal_Sample_Time
        self.RZERO = AvRs / self.RSAIR
        return self.RZERO

    # Function to calculate the voltage from raw PM data
    def Get_PMVolt(self, cmd):
        self.PMVolt = ((3300.00 / self.MaxADC) * float(self.Get_rawdata(cmd)) * 11.00)
        return self.PMVolt

    # Function to calculate the densisty of the particulate matter detected
    def Get_PMDensity(self, cmd):
        self.Get_PMVolt(cmd)
        if self.PMVolt >= NODUSTVOLTAGE:
            self.PMVolt -= NODUSTVOLTAGE
            self.PMDensity = self.PMVolt * COVRATIO
        else:
            self.PMDensity = 0
        return self.PMDensity

    # Function to correct the RS/R0 ratio based on temperature and relative humidity
    def Corrected_RS_RO(self, cmd, temperature, humidity, Const_33, Const_85):
        temperature = float(temperature)
        humidity = float(humidity)
        rsro_ambtemp_33RH = (Const_33[0] * pow(temperature, 3)) + (Const_33[1] * pow(temperature, 2)) + (Const_33[2] * temperature) + Const_33[3]
        rsro_ambtemp_85RH = (Const_85[0] * pow(temperature, 3)) + (Const_85[1] * pow(temperature, 2)) + (Const_85[2] * temperature) + Const_85[3]
        rsro_ambtemp_65RH = ((65.0 - 33.0) / (85.0 - 65.0) * (rsro_ambtemp_85RH - rsro_ambtemp_33RH) + rsro_ambtemp_33RH) * 1.102
        if humidity < 65:
            rsro_ambtemp_ambRH = (humidity - 33) / (65 - 33) * (rsro_ambtemp_65RH - rsro_ambtemp_33RH) + rsro_ambtemp_33RH
        else:
            rsro_ambtemp_ambRH = (humidity - 65) / (85 - 65) * (rsro_ambtemp_85RH - rsro_ambtemp_65RH) + rsro_ambtemp_65RH
        # calculate correction factor
        refrsro_at_20C65RH = 1.00
        rsroCorrPct = 1 + (refrsro_at_20C65RH - rsro_ambtemp_ambRH) / refrsro_at_20C65RH
        correctedrsro = rsroCorrPct * (self.Get_RSR0Ratio(cmd))
        return correctedrsro

    # Function to correct the RS/R0 ratio based on temperature and relative humidity for the MQ2
    def Corrected_RS_RO_MQ2(self, cmd, temperature, humidity, Const_30, Const_60, Const_85):
        temperature = float(temperature)
        humidity = float(humidity)
        rsro_ambtemp_30RH = (Const_30[0] * pow(temperature, 3)) + (Const_30[1] * pow(temperature, 2)) + (Const_30[2] * temperature) + Const_30[3]
        rsro_ambtemp_60RH = (Const_60[0] * pow(temperature, 3)) + (Const_60[1] * pow(temperature, 2)) + (Const_60[2] * temperature) + Const_60[3]
        rsro_ambtemp_85RH = (Const_85[0] * pow(temperature, 3)) + (Const_85[1] * pow(temperature, 2)) + (Const_85[2] * temperature) + Const_85[3]

        if humidity < 60:
            rsro_ambtemp_ambRH = (humidity - 30) / (60 - 30) * (rsro_ambtemp_60RH - rsro_ambtemp_30RH) + rsro_ambtemp_30RH
        else:
            rsro_ambtemp_ambRH = (humidity - 60) / (85 - 60) * (rsro_ambtemp_85RH - rsro_ambtemp_60RH) + rsro_ambtemp_60RH
        # Calculate correction factor
        refrsro_at_20C60RH = 1.00
        rsroCorrPct = 1 + (refrsro_at_20C60RH - rsro_ambtemp_ambRH) / refrsro_at_20C60RH
        correctedrsro = rsroCorrPct * (self.Get_RSR0Ratio(cmd))
        return correctedrsro


class Gas:

    def __init__(self, name, rsromax, rsromin, gradient, intercept, threshold, LED=None):
        self.name = name
        self._device = get_bus()
        self.min = rsromin
        self.max = rsromax
        self.gradient = gradient
        self.intercept = intercept
        self.threshold = threshold
        self.LED = LED if LED is not None else Off
        self.PPM = 0.0

    # Function to calculate the PPM of the specific gas
    def Get_PPM(self, rs_ro):
        if rs_ro <= 0 or rs_ro == float('inf'):
            self.PPM = 0.0
        else:
            self.PPM = pow(10, ((self.gradient * (log10(rs_ro))) + self.intercept))
        return self.PPM

    # Function to set the LED Color, used for setting alarms points
    def Set_LED(self, LEDColour):  # LEDColour = Red , Green, Blue Brightness values from 0 - 255 in an array
        self._device.write_byte(I2C_Addr, LEDcmd)
        for x in range(3):
            self._device.write_byte(I2C_Addr, LEDColour[x])

    # Function to check the PPM value against the predefined threshold
    def Chk_threshold(self):
        if self.PPM < self.threshold:
            self.Set_LED(Green)
        elif self.PPM == self.threshold:
            self.Set_LED(Orange)
        else:
            self.Set_LED(self.LED)
