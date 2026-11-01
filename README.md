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

   The installer installs `python3-smbus`, `python3-gpiozero` and
   `i2c-tools`, enables the I2C interface and adds your user to the `i2c`
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

The MQ sensors need to heat up, so the script waits 15 minutes before it
starts logging. Readings are written every 30 seconds to
`Sensly_<date>_<time>.csv` in the current directory and echoed to the
terminal. Press Ctrl-C to stop.

Options:

| Flag | Default | Meaning |
| --- | --- | --- |
| `--warmup SECONDS` | 900 | Heat-up time before logging. Use `0` for a quick test. |
| `--interval SECONDS` | 30 | Time between samples. |
| `--output FILE` | auto | CSV file to write. |

## Calibrating

Put the HAT in clean air and run:

```bash
python3 Sensly_Calibration.py
```

It warms up for 10 minutes, then prints and logs a running R0 estimate for
each sensor. Let it run until the values settle, press Ctrl-C, and copy the
printed `R0 = [...]` line into the `R0` list near the top of `Sensly.py`.

## Running at boot (optional)

Create `/etc/systemd/system/sensly.service`:

```ini
[Unit]
Description=Sensly air quality logger
After=multi-user.target

[Service]
User=pi
WorkingDirectory=/home/pi/sensly
ExecStart=/usr/bin/python3 /home/pi/sensly/Sensly.py
Restart=on-failure

[Install]
WantedBy=multi-user.target
```

Then:

```bash
sudo systemctl enable --now sensly.service
```

Adjust `User` and the paths to match where you cloned the repository.

## Troubleshooting

- **`Could not open /dev/i2c-1`**: I2C is not enabled. Run
  `sudo raspi-config nonint do_i2c 0` and reboot.
- **`I2C read from Sensly HAT ... failed`**: the HAT is not seated properly
  or is not powered. Check `i2cdetect -y 1` shows address `05`.
- **Permission denied on GPIO or I2C**: make sure your user is in the `gpio`
  and `i2c` groups (`groups $USER`) and that you logged out and in again
  after running the installer.
