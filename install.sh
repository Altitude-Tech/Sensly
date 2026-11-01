#!/bin/bash
# One-shot setup for the Sensly HAT on Raspberry Pi OS (Bookworm or later).
# Tested target: Raspberry Pi 4.  Run with:  bash install.sh
set -e

echo "==> Installing Python dependencies"
sudo apt-get update
sudo apt-get install -y python3 python3-smbus python3-gpiozero i2c-tools
# smbus2 is preferred when available; fall back silently to python3-smbus
sudo apt-get install -y python3-smbus2 2>/dev/null || true

echo "==> Enabling the I2C interface"
sudo raspi-config nonint do_i2c 0

echo "==> Adding $USER to the i2c and gpio groups"
sudo usermod -aG i2c,gpio "$USER"

echo
echo "Done. Reboot (sudo reboot), then check the HAT is visible with:"
echo "    i2cdetect -y 1"
echo "You should see 05 (Sensly MCU) and 76 (BME280)."
echo "Then run:   python3 Sensly.py"
