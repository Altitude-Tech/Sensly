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
MQ7_MAX_VALID_RATIO = 1000.0
_last_valid_mq7 = None


def take_reading(sensor, MQ2cmd, MQ7cmd, MQ135cmd, PMcmd):
    """Read every sensor once and return a dict of calculated values."""
    global _last_valid_mq7
    # Initialise the gases in an array (all PPM values start at 0)
    MQ2_Gases = [0, 0, 0, 0, 0, 0]      # CO, CH4, Alcohol, H2, Propane, LPG
    MQ7_Gases = [0, 0, 0, 0, 0]         # Alcohol, CH4, LPG, CO, H2
    MQ135_Gases = [0, 0, 0, 0, 0, 0]    # CO, NH4, CO2, Ethanol, Methly, Acetone

    # Fetch the current temperature, humidity and pressure
    temperature = sensor.read_temperature()
    humidity = sensor.read_humidity()
    pressure = sensor.read_pressure() / 100.0   # Pa -> hPa

    # Correct the RS/R0 ratio to account for temperature and humidity,
    # then calculate the PPM for each gas
    MQ2Rs_R0 = MQ2.Corrected_RS_RO_MQ2(MQ2cmd, temperature, humidity, MQ2_t_30H, MQ2_t_60H, MQ2_t_85H)
    Get_MQ2PPM(MQ2Rs_R0, MQ2_Gases)

    MQ7Rs_R0 = MQ7.Corrected_RS_RO(MQ7cmd, temperature, humidity, MQ7_t_33H, MQ7_t_85H)
    if MQ7Rs_R0 > MQ7_MAX_VALID_RATIO:
        # Heater in its high phase: hold the previous valid reading
        MQ7Rs_R0 = _last_valid_mq7
    else:
        _last_valid_mq7 = MQ7Rs_R0
    if MQ7Rs_R0 is not None:
        Get_MQ7PPM(MQ7Rs_R0, MQ7_Gases)

    MQ135Rs_R0 = MQ135.Corrected_RS_RO(MQ135cmd, temperature, humidity, MQ135_t_33H, MQ135_t_85H)
    Get_MQ135PPM(MQ135Rs_R0, MQ135_Gases)

    pm10 = PM.Get_PMDensity(PMcmd)

    return {
        'temperature': round(temperature, 2),
        'humidity': round(humidity, 1),
        'pressure': round(pressure, 1),
        'co': round(MQ7_Gases[3], 2),
        'nh3': round(MQ135_Gases[1], 2),
        'co2': round(MQ135_Gases[2], 2),
        'methyl': round(MQ135_Gases[4], 2),
        'acetone': round(MQ135_Gases[5], 2),
        'methane': round(MQ2_Gases[1], 2),
        'lpg': round(MQ2_Gases[5], 2),
        'hydrogen': round(MQ2_Gases[3], 2),
        'propane': round(MQ2_Gases[4], 2),
        'pm10': round(pm10, 2),
        'mq2_ratio': round(MQ2Rs_R0, 4),
        'mq7_ratio': round(MQ7Rs_R0, 4) if MQ7Rs_R0 is not None else None,
        'mq135_ratio': round(MQ135Rs_R0, 4),
    }


def load_mqtt_config(path):
    """Read the [mqtt] section of the config file into a dict."""
    if not os.path.exists(path):
        sys.exit("MQTT config file not found: %s\n"
                 "Copy sensly.conf.example to sensly.conf and fill in your broker details." % path)
    parser = configparser.ConfigParser()
    parser.read(path)
    if 'mqtt' not in parser:
        sys.exit("No [mqtt] section in %s" % path)
    section = parser['mqtt']
    return {
        'host': section.get('host', 'homeassistant.local'),
        'port': section.getint('port', 1883),
        'username': section.get('username', '') or None,
        'password': section.get('password', '') or None,
        'device_id': section.get('device_id', 'sensly_hat'),
        'device_name': section.get('device_name', 'Sensly HAT'),
        'discovery_prefix': section.get('discovery_prefix', 'homeassistant'),
    }


def main():
    parser = argparse.ArgumentParser(description="Log air-quality data from the Sensly HAT to a CSV file.")
    parser.add_argument("--warmup", type=int, default=900,
                        help="seconds to let the MQ sensors heat up before logging (default: 900)")
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

    publisher = None
    if args.mqtt:
        from sensly_mqtt import SenslyMQTT
        publisher = SenslyMQTT(load_mqtt_config(args.config))
        publisher.connect()

    try:
        if args.warmup > 0:
            print("Sensly is warming up, please wait %d minutes" % (args.warmup // 60), flush=True)
            time.sleep(args.warmup)
            print("Heating completed", flush=True)

        while True:
            reading = take_reading(sensor, MQ2cmd, MQ7cmd, MQ135cmd, PMcmd)

            # CSV row, same column order as the header line
            data = [
                time.strftime('%H:%M:%S'),
                reading['co'], reading['nh3'], reading['co2'], reading['methyl'],
                reading['acetone'], reading['methane'], reading['lpg'],
                reading['hydrogen'], reading['propane'], reading['pm10'],
            ]
            with open(datafile, 'a') as f2:
                f2.write(','.join(str(d) for d in data) + '\n')
            mq7 = reading['mq7_ratio']
            print("%s  T=%.1fC RH=%.0f%%  MQ2=%.3f MQ7=%s MQ135=%.3f  PM=%.1f"
                  % (data[0], reading['temperature'], reading['humidity'],
                     reading['mq2_ratio'], "%.3f" % mq7 if mq7 is not None else "warming",
                     reading['mq135_ratio'], reading['pm10']), flush=True)

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
