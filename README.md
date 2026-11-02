# Sensly

Python scripts to log air-quality data from the Sensly HAT, plus a script to
calibrate the MQ gas sensors.

Ported to Python 3 and tested against the libraries shipped with Raspberry Pi
OS Bookworm and later. Works on the Raspberry Pi 4 (and other 40-pin models).

## Setup on a Raspberry Pi 4

1. Fit the Sensly HAT on the 40-pin header and boot Raspberry Pi OS.
2. Clone this repository and run the installer:

   ```bash
   git clone https://github.com/matthewgcampbell/sensly.git
   cd sensly
   bash install.sh
   sudo reboot
   ```

   The installer installs `python3-smbus`, `python3-gpiozero`,
   `python3-paho-mqtt` and `i2c-tools`, enables the I2C interface and adds your user to the `i2c`
   and `gpio` groups.

3. After the reboot, confirm the HAT is detected:

   ```bash
   i2cdetect -y 1
   ```

   You should see `05` (the Sensly microcontroller) and `76` (the BME280
   temperature/humidity sensor).

## Logging data

```bash
python3 Sensly.py
```

The MQ sensors need to heat up after a power cycle, so the script waits 15
minutes before logging gases. The heaters stay powered as long as the Pi is
on, so a restart of the script after the Pi has been up that long skips the
wait. Readings are written every 30 seconds to
`Sensly_<date>_<time>.csv` in the current directory and echoed to the
terminal. Press Ctrl-C to stop.

Options:

| Flag | Default | Meaning |
| --- | --- | --- |
| `--warmup SECONDS` | 900 | Heat-up time before logging. Use `0` for a quick test. |
| `--interval SECONDS` | 30 | Time between samples. |
| `--output FILE` | auto | CSV file to write. |
| `--mqtt` | off | Also publish to Home Assistant over MQTT. |
| `--config FILE` | sensly.conf | MQTT settings file. |

## Calibrating

The PPM figures depend on each sensor's clean-air resistance (R0), which
differs from board to board. The built-in defaults came from the original
author's HAT, so calibrate once your own has been running for a day:

```bash
sudo systemctl stop sensly
python3 Sensly_Calibration.py
sudo systemctl start sensly
```

Put the HAT somewhere with clean air first: a ventilated room away from
cooking, smoke, solvents and people breathing on it. The script warms up for
10 minutes, samples for an hour, and writes the R0 values into `sensly.conf`.
The logger reads them from there on its next start. Repeat every few months,
as MQ sensors drift with age.

## CO2 against a reference meter

The original MQ135 lookup table only produces a CO2 figure once the air is
already stale, and reports 0 in clean air. If you have a trusted CO2 meter
(an NDIR sensor such as an AirGradient or Aranet), anchor the Sensly to it:
note the MQ135 RS/R0 ratio (`sensor.sensly_hat_mq135_rs_r0`, averaged over
a few minutes) at the same moment the reference meter reads a stable value,
and put both under `[calibration]` in `sensly.conf`:

```ini
co2_ref_ppm = 440
co2_ref_ratio = 2.72
```

CO2 then follows the datasheet curve across the whole range, scaled so that
ratio reads as that many ppm. Re-anchor after each R0 calibration.

## MQ7 heater cycle

The HAT cycles the MQ7 heater between high and low power. During the high
phase MQ7 cannot be read, and the extra current pulls the 5 V rail down
enough to shift the MQ2 and MQ135 readings as well, especially on jumper
wires. The logger and the calibration script only use samples from the low
phase and hold the previous values during the high phase.

## Temperature and humidity offsets

The BME280 sits next to three heated gas sensors and reads warm. The
`[calibration]` section of `sensly.conf` has `temperature_offset` and
`humidity_offset` values that are added to its readings. Compare against a
trusted thermometer in the same room after the HAT has been running for an
hour and set the difference there. The default offset of -10.6 C is what the
original author used with the HAT stacked directly on a Pi.

## Optional particulate sensor

The HAT has a "PM 2.5 Header" for an external dust sensor. If nothing is
plugged into it, set `pm_attached = no` under `[sensors]` in `sensly.conf`
so a meaningless PM10 reading of zero is not logged or sent to Home
Assistant.

## Home Assistant

The logger can publish every reading to Home Assistant over MQTT. Temperature,
humidity and pressure are sent from the moment it starts; the gas readings
show as unknown until the warm-up finishes. It uses
MQTT discovery, so the sensors appear on their own under a "Sensly HAT"
device with the right units and icons. No Home Assistant configuration
changes are needed beyond having the Mosquitto broker add-on and the MQTT
integration installed.

1. In Home Assistant, create a user for the Pi under Settings -> People ->
   Users (for example `sensly`). The Mosquitto add-on uses Home Assistant
   users for MQTT logins.
2. On the Pi, create the config file and fill in the broker address and
   that login:

   ```bash
   cp sensly.conf.example sensly.conf
   nano sensly.conf
   ```

3. Run with the `--mqtt` flag:

   ```bash
   python3 Sensly.py --mqtt
   ```

Within a few seconds the device appears under Settings -> Devices &
Services -> MQTT. Entities are named `sensor.sensly_hat_temperature`,
`sensor.sensly_hat_co2`, `sensor.sensly_hat_pm10` and so on. The raw RS/R0
ratios are included as diagnostic entities for calibration checks.
Readings expire after 10 minutes without an update, so the entities show
as unavailable if the Pi stops.

## Running at boot

A systemd unit is included. If you cloned to `/home/pi/Sensly`:

```bash
sudo cp sensly.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now sensly
```

Watch the output with `journalctl -u sensly -f`. Edit the `User`,
`WorkingDirectory` and `ExecStart` lines in the unit file first if your
path or username differ, and drop `--mqtt` from `ExecStart` if you only
want CSV logging.

## Troubleshooting

- **`Could not open /dev/i2c-1`**: I2C is not enabled. Run
  `sudo raspi-config nonint do_i2c 0` and reboot.
- **`I2C read from Sensly HAT ... failed`**: the HAT is not seated properly
  or is not powered. Check `i2cdetect -y 1` shows address `05`.
- **Permission denied on GPIO or I2C**: make sure your user is in the `gpio`
  and `i2c` groups (`groups $USER`) and that you logged out and in again
  after running the installer.
