#!/usr/bin/env python3
"""Sensly HAT air-quality logger.

Logs gas PPM values and particulate density to a timestamped CSV file.
Python 3 port for Raspberry Pi 4 running Raspberry Pi OS Bookworm or later.

Usage:
    python3 Sensly.py                 # 15 minute warm-up, sample every 30 s
    python3 Sensly.py --warmup 0      # skip warm-up (readings will be off)
    python3 Sensly.py --interval 10   # sample every 10 s
    python3 Sensly.py --mqtt          # also publish to Home Assistant via MQTT
                                      # (broker settings in sensly.conf)
"""

import argparse
import configparser
import os
import sys
import time

from Sensors import Sensor, Gas, reset_hat
from bme_combo import BME280, BME280_OSAMPLE_8


def Reset():
    """Reset the Sensly HAT via its reset line (GPIO 23)."""
    reset_hat(0.5)


# Sensly Constants 
R0 = [3120.5010, 1258.8822, 2786.3375]      # MQ2, MQ7, MQ135 R0 resistance (needed for PPM calculation).
                                            # Defaults from the original author's board. Run Sensly_Calibration.py
                                            # in clean air to measure your own; it stores them in sensly.conf.
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

# Initialise the gases

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

#functions
   
'''
This Function checks the RS/R0 value to select which gas is being detected
'''
def Get_MQ2PPM(MQ2Rs_R0, Gases):
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
'''
This Function checks the RS/R0 value to select which gas is being detected
'''
def Get_MQ7PPM(MQ7Rs_R0, Gases):
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
'''
This Function checks the RS/R0 value to select which gas is being detected
'''           
def Get_MQ135PPM(MQ135Rs_R0, Gases):
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


# The MQ7 heater is cycled by the HAT firmware (high heat to clean the
# sensor, then low heat to measure). During the high-heat phase the sensor
# reads almost zero, giving an RS/R0 ratio in the tens of thousands. Ratios
# above this limit are treated as invalid and the last good value is kept.
#
# The extra heater current in that phase also pulls the HAT's 5 V rail down
# slightly (noticeably so on jumper wires), which shifts the MQ2 and MQ135
# readings. Their values from the previous low-heat sample are held too, so
# every reported ratio comes from the same, quieter supply condition.
MQ7_MAX_VALID_RATIO = 1000.0
_last_valid_mq7 = None
_last_valid_mq2 = None
_last_valid_mq135 = None

# Default exponent of the MQ135 CO2 curve (slope of the datasheet's log-log
# line). Used by the reference-anchored CO2 conversion, see co2_ref_* in
# sensly.conf.
DEFAULT_CO2_EXPONENT = -2.7979


def co2_from_reference(ratio, config):
    """CO2 in ppm from the MQ135 ratio, anchored to a reference reading.

    ppm = ref_ppm * (ratio / ref_ratio) ** exponent, where ref_ratio is the
    MQ135 RS/R0 ratio observed when a trusted CO2 meter read ref_ppm.
    Unlike the original lookup table this works across the whole range, so
    clean air reports a realistic 400-500 ppm instead of 0.
    """
    if ratio <= 0:
        return 0.0
    return config['co2_ref_ppm'] * pow(ratio / config['co2_ref_ratio'], config['co2_exponent'])


def take_reading(sensor, MQ2cmd, MQ7cmd, MQ135cmd, PMcmd, config, warm=True):
    """Read every sensor once and return a dict of calculated values.

    While warm is False (sensors still heating) the gas values are None.
    """
    global _last_valid_mq7, _last_valid_mq2, _last_valid_mq135
    # Initialise the gases in an array (all PPM values start at 0)
    MQ2_Gases = [0, 0, 0, 0, 0, 0]      # CO, CH4, Alcohol, H2, Propane, LPG
    MQ7_Gases = [0, 0, 0, 0, 0]         # Alcohol, CH4, LPG, CO, H2
    MQ135_Gases = [0, 0, 0, 0, 0, 0]    # CO, NH4, CO2, Ethanol, Methly, Acetone

    # Fetch the current temperature, humidity and pressure
    temperature = sensor.read_temperature() + config['temperature_offset']
    humidity = min(100.0, max(0.0, sensor.read_humidity() + config['humidity_offset']))
    pressure = sensor.read_pressure() / 100.0   # Pa -> hPa

    # Correct the RS/R0 ratio to account for temperature and humidity,
    # then calculate the PPM for each gas
    MQ2Rs_R0 = MQ2.Corrected_RS_RO_MQ2(MQ2cmd, temperature, humidity, MQ2_t_30H, MQ2_t_60H, MQ2_t_85H)
    MQ7Rs_R0 = MQ7.Corrected_RS_RO(MQ7cmd, temperature, humidity, MQ7_t_33H, MQ7_t_85H)
    MQ135Rs_R0 = MQ135.Corrected_RS_RO(MQ135cmd, temperature, humidity, MQ135_t_33H, MQ135_t_85H)

    if MQ7Rs_R0 > MQ7_MAX_VALID_RATIO:
        # MQ7 heater in its high phase: hold the previous low-phase readings
        if _last_valid_mq7 is None:
            # No low-phase sample seen yet (just started): the MQ2 and
            # MQ135 values are from the sagged supply, so report nothing
            # rather than publish a spike.
            warm = False
            MQ7Rs_R0 = None
            MQ2Rs_R0 = None
            MQ135Rs_R0 = None
        else:
            MQ7Rs_R0 = _last_valid_mq7
            MQ2Rs_R0 = _last_valid_mq2
            MQ135Rs_R0 = _last_valid_mq135
    else:
        _last_valid_mq7 = MQ7Rs_R0
        _last_valid_mq2 = MQ2Rs_R0
        _last_valid_mq135 = MQ135Rs_R0

    if MQ2Rs_R0 is not None:
        Get_MQ2PPM(MQ2Rs_R0, MQ2_Gases)
    if MQ7Rs_R0 is not None:
        Get_MQ7PPM(MQ7Rs_R0, MQ7_Gases)
    if MQ135Rs_R0 is not None:
        Get_MQ135PPM(MQ135Rs_R0, MQ135_Gases)
        if config['co2_ref_ratio']:
            MQ135_Gases[2] = co2_from_reference(MQ135Rs_R0, config)

    pm10 = PM.Get_PMDensity(PMcmd) if config['pm_attached'] else None

    def gas(value):
        return round(value, 2) if warm else None

    reading = {
        'temperature': round(temperature, 2),
        'humidity': round(humidity, 1),
        'pressure': round(pressure, 1),
        'co': gas(MQ7_Gases[3]),
        'nh3': gas(MQ135_Gases[1]),
        'co2': gas(MQ135_Gases[2]),
        'methyl': gas(MQ135_Gases[4]),
        'acetone': gas(MQ135_Gases[5]),
        'methane': gas(MQ2_Gases[1]),
        'lpg': gas(MQ2_Gases[5]),
        'hydrogen': gas(MQ2_Gases[3]),
        'propane': gas(MQ2_Gases[4]),
        'mq2_ratio': round(MQ2Rs_R0, 4) if MQ2Rs_R0 is not None else None,
        'mq7_ratio': round(MQ7Rs_R0, 4) if MQ7Rs_R0 is not None else None,
        'mq135_ratio': round(MQ135Rs_R0, 4) if MQ135Rs_R0 is not None else None,
    }
    if config['pm_attached']:
        reading['pm10'] = round(pm10, 2) if warm else None
    return reading


# Default temperature offset in degrees C. The BME280 sits next to three
# heated gas sensors and reads warm; this is subtracted from its reading.
# The original Sensly code used -10.63 for a HAT stacked on a Pi. Override
# it (and the humidity offset) in sensly.conf under [calibration].
DEFAULT_TEMPERATURE_OFFSET = -10.633
DEFAULT_HUMIDITY_OFFSET = 0.0


def system_uptime():
    """Seconds since the Pi booted (0 if unknown)."""
    try:
        with open('/proc/uptime') as f:
            return float(f.read().split()[0])
    except (OSError, ValueError, IndexError):
        return 0.0


def load_config(path, need_mqtt=False):
    """Read sensly.conf. Missing file or sections fall back to defaults."""
    parser = configparser.ConfigParser()
    if os.path.exists(path):
        parser.read(path)
    elif need_mqtt:
        sys.exit("Config file not found: %s\n"
                 "Copy sensly.conf.example to sensly.conf and fill in your broker details." % path)

    mqtt = parser['mqtt'] if 'mqtt' in parser else {}
    cal = parser['calibration'] if 'calibration' in parser else {}
    sensors = parser['sensors'] if 'sensors' in parser else {}

    def getfloat(section, key, default):
        try:
            return float(section.get(key, default))
        except (TypeError, ValueError):
            sys.exit("Bad number for %s in %s" % (key, path))

    def getbool(section, key, default):
        value = str(section.get(key, default)).strip().lower()
        return value in ('1', 'yes', 'true', 'on')

    if need_mqtt and not mqtt:
        sys.exit("No [mqtt] section in %s" % path)

    return {
        'mqtt': {
            'host': mqtt.get('host', 'homeassistant.local'),
            'port': int(mqtt.get('port', 1883)),
            'username': mqtt.get('username', '') or None,
            'password': mqtt.get('password', '') or None,
            'device_id': mqtt.get('device_id', 'sensly_hat'),
            'device_name': mqtt.get('device_name', 'Sensly HAT'),
            'discovery_prefix': mqtt.get('discovery_prefix', 'homeassistant'),
        },
        'temperature_offset': getfloat(cal, 'temperature_offset', DEFAULT_TEMPERATURE_OFFSET),
        'humidity_offset': getfloat(cal, 'humidity_offset', DEFAULT_HUMIDITY_OFFSET),
        'r0_mq2': getfloat(cal, 'r0_mq2', R0[0]),
        'r0_mq7': getfloat(cal, 'r0_mq7', R0[1]),
        'r0_mq135': getfloat(cal, 'r0_mq135', R0[2]),
        # CO2 reference anchor: both must be set to enable the reference curve
        'co2_ref_ppm': getfloat(cal, 'co2_ref_ppm', 0),
        'co2_ref_ratio': getfloat(cal, 'co2_ref_ratio', 0),
        'co2_exponent': getfloat(cal, 'co2_exponent', DEFAULT_CO2_EXPONENT),
        'pm_attached': getbool(sensors, 'pm_attached', 'yes'),
    }


def main():
    parser = argparse.ArgumentParser(description="Log air-quality data from the Sensly HAT to a CSV file.")
    parser.add_argument("--warmup", type=int, default=900,
                        help="seconds the MQ sensors need to heat up after power-on (default: 900); "
                             "time the Pi has already been up is credited, so a restart does not wait again")
    parser.add_argument("--interval", type=float, default=30,
                        help="seconds between samples (default: 30)")
    parser.add_argument("--output", default=None,
                        help="CSV file to write (default: ./Sensly_<date>_<time>.csv)")
    parser.add_argument("--mqtt", action="store_true",
                        help="publish readings to Home Assistant over MQTT (see sensly.conf)")
    parser.add_argument("--config", default=os.path.join(os.path.dirname(os.path.abspath(__file__)), "sensly.conf"),
                        help="config file with MQTT broker settings (default: sensly.conf next to this script)")
    args = parser.parse_args()

    Reset()
    # Give the HAT's microcontroller a moment to come back up after reset
    time.sleep(1)

    sensor = BME280(mode=BME280_OSAMPLE_8)

    datafile = args.output or time.strftime('./Sensly_%d-%m-%Y_%H_%M_%S.csv')
    with open(datafile, 'w') as f1:
        f1.write('Time, Carbon Monoxide PPM, Ammonia PPM, Carbon Dioxide PPM, Methly PPM, Acetone PPM, Methane PPM, LPG PPM, Hydrogen PPM, Propane PPM, PM10 \n')
    print("Logging to %s" % datafile, flush=True)

    # Set commands for getting data from sensors
    MQ2cmd = 0x01
    MQ7cmd = 0x02
    MQ135cmd = 0x03
    PMcmd = 0x04

    config = load_config(args.config, need_mqtt=args.mqtt)
    # Calibrated R0 values from sensly.conf override the built-in defaults
    MQ2.R0 = config['r0_mq2']
    MQ7.R0 = config['r0_mq7']
    MQ135.R0 = config['r0_mq135']
    print("Using R0: MQ2=%.1f MQ7=%.1f MQ135=%.1f" % (MQ2.R0, MQ7.R0, MQ135.R0), flush=True)

    publisher = None
    if args.mqtt:
        from sensly_mqtt import SenslyMQTT
        publisher = SenslyMQTT(config['mqtt'], include_pm=config['pm_attached'])
        publisher.connect()

    # The MQ heaters run from the HAT's 5 V rail whenever the Pi is powered,
    # so they only need the warm-up after a power cycle, not after a restart
    # of this script. Credit the time the Pi has already been up.
    warmup = max(0, args.warmup - int(system_uptime()))
    started = time.monotonic()
    warm = warmup <= 0
    if not warm:
        print("Sensly is warming up, gas readings start in %d minutes" % (warmup // 60), flush=True)
    elif args.warmup > 0:
        print("Pi has been up longer than the warm-up time, skipping warm-up", flush=True)

    try:
        while True:
            if not warm and time.monotonic() - started >= warmup:
                warm = True
                print("Heating completed", flush=True)

            reading = take_reading(sensor, MQ2cmd, MQ7cmd, MQ135cmd, PMcmd, config, warm)
            now = time.strftime('%H:%M:%S')

            if warm and reading['co'] is not None:
                # CSV row, same column order as the header line
                data = [
                    now,
                    reading['co'], reading['nh3'], reading['co2'], reading['methyl'],
                    reading['acetone'], reading['methane'], reading['lpg'],
                    reading['hydrogen'], reading['propane'], reading.get('pm10', ''),
                ]
                with open(datafile, 'a') as f2:
                    f2.write(','.join(str(d) for d in data) + '\n')

            def fmt(value):
                return "%.3f" % value if value is not None else "waiting"
            print("%s  T=%.1fC RH=%.0f%%  MQ2=%s MQ7=%s MQ135=%s%s"
                  % (now, reading['temperature'], reading['humidity'],
                     fmt(reading['mq2_ratio']), fmt(reading['mq7_ratio']), fmt(reading['mq135_ratio']),
                     "  PM=%s" % reading['pm10'] if 'pm10' in reading else ""), flush=True)

            if publisher is not None:
                publisher.publish(reading)

            time.sleep(args.interval)

    except KeyboardInterrupt:
        print("Bye")
    finally:
        if publisher is not None:
            publisher.close()


if __name__ == "__main__":
    main()
