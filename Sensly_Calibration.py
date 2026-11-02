#!/usr/bin/env python3
"""Sensly HAT calibration script.

Run this with the HAT in clean air (a well-ventilated room, or outdoors,
away from cooking, smoke, solvents and people breathing on it). It averages
the sensor resistance over many samples and tracks a running R0 estimate
for each MQ sensor. When it finishes it writes the values into sensly.conf
so Sensly.py picks them up on its next start.

Usage:
    sudo systemctl stop sensly                 # the logger must not be using the HAT
    python3 Sensly_Calibration.py              # 10 min warm-up, then 60 min of sampling
    sudo systemctl start sensly

    python3 Sensly_Calibration.py --warmup 0 --duration 600   # quick 10 minute run
    python3 Sensly_Calibration.py --duration 0                # run until Ctrl-C
"""

import argparse
import configparser
import os
import time

from Sensors import Sensor, reset_hat

DEFAULT_CONFIG = os.path.join(os.path.dirname(os.path.abspath(__file__)), "sensly.conf")


def save_r0(path, r0_mq2, r0_mq7, r0_mq135):
    """Write the R0 values into the [calibration] section of the config file."""
    parser = configparser.ConfigParser()
    if os.path.exists(path):
        parser.read(path)
    if 'calibration' not in parser:
        parser['calibration'] = {}
    parser['calibration']['r0_mq2'] = "%.4f" % r0_mq2
    parser['calibration']['r0_mq7'] = "%.4f" % r0_mq7
    parser['calibration']['r0_mq135'] = "%.4f" % r0_mq135
    with open(path, 'w') as f:
        parser.write(f)


def main():
    parser = argparse.ArgumentParser(description="Calibrate the Sensly HAT MQ sensors in clean air.")
    parser.add_argument("--warmup", type=int, default=600,
                        help="seconds to let the MQ sensors heat up before sampling (default: 600)")
    parser.add_argument("--duration", type=int, default=3600,
                        help="seconds to sample for before saving (default: 3600, 0 = until Ctrl-C)")
    parser.add_argument("--samples", type=int, default=300,
                        help="samples per averaging window (default: 300)")
    parser.add_argument("--config", default=DEFAULT_CONFIG,
                        help="config file to write the R0 values into (default: sensly.conf next to this script)")
    parser.add_argument("--no-save", action="store_true",
                        help="only print the values, do not write the config file")
    args = parser.parse_args()

    # Reset Sensly HAT
    reset_hat(1.0)
    time.sleep(1)

    # Sensly Constants
    RSAir = [9.5, 27, 3.62]     # RS/R0 ratio of each sensor in clean air, from the datasheets
    Cal_Sample_Time = args.samples

    MQ2 = Sensor('MQ2', 0, RSAir[0])
    MQ7 = Sensor('MQ7', 0, RSAir[1])
    MQ135 = Sensor('MQ135', 0, RSAir[2])

    datafile = time.strftime('./Sensly_Calibration_%d-%m-%Y_%H_%M_%S.csv')
    with open(datafile, 'w') as f1:
        f1.write('Time, MQ2RZero, MQ7RZero, MQ135RZero\n')
    print("Logging to %s" % datafile, flush=True)

    # Set commands for getting data from sensors
    MQ2cmd = 0x01
    MQ7cmd = 0x02
    MQ135cmd = 0x03

    # Running averages (None until the first window completes)
    r0_mq2 = r0_mq7 = r0_mq135 = None
    windows = 0

    try:
        if args.warmup > 0:
            print("Warming up for %d minutes" % (args.warmup // 60), flush=True)
            time.sleep(args.warmup)
        if args.duration > 0:
            print("Heating completed, calibrating for %d minutes (Ctrl-C to stop early and save)"
                  % (args.duration // 60), flush=True)
        else:
            print("Heating completed, calibrating until Ctrl-C", flush=True)
        started = time.monotonic()

        while args.duration <= 0 or time.monotonic() - started < args.duration:
            AvRs_MQ2 = AvRs_MQ7 = AvRs_MQ135 = 0.0
            valid = 0

            for _ in range(Cal_Sample_Time):
                rs2 = MQ2.Get_RS(MQ2cmd)
                time.sleep(0.01)
                rs7 = MQ7.Get_RS(MQ7cmd)
                time.sleep(0.01)
                rs135 = MQ135.Get_RS(MQ135cmd)
                time.sleep(0.01)
                # Only keep samples from the MQ7 heater's low phase. In the
                # high phase MQ7 reads near zero and the extra heater current
                # sags the 5 V rail, shifting the MQ2 and MQ135 readings too.
                if rs7 < 1e7:
                    AvRs_MQ2 += rs2
                    AvRs_MQ7 += rs7
                    AvRs_MQ135 += rs135
                    valid += 1

            if not valid:
                continue
            AvRs_MQ2 /= valid
            AvRs_MQ7 /= valid
            AvRs_MQ135 /= valid

            # Cumulative running average of R0 = RS_air / (RS/R0 in clean air)
            windows += 1
            new2 = AvRs_MQ2 / MQ2.RSAIR
            new7 = AvRs_MQ7 / MQ7.RSAIR
            new135 = AvRs_MQ135 / MQ135.RSAIR
            r0_mq2 = new2 if r0_mq2 is None else r0_mq2 + (new2 - r0_mq2) / windows
            r0_mq7 = new7 if r0_mq7 is None else r0_mq7 + (new7 - r0_mq7) / windows
            r0_mq135 = new135 if r0_mq135 is None else r0_mq135 + (new135 - r0_mq135) / windows

            now = time.strftime('%H:%M:%S')
            with open(datafile, 'a') as f2:
                f2.write('%s,%s,%s,%s\n' % (now, r0_mq2, r0_mq7, r0_mq135))
            print("%s  R0: MQ2=%.1f MQ7=%.1f MQ135=%.1f  (%d of %d samples in MQ7 low phase)"
                  % (now, r0_mq2, r0_mq7, r0_mq135, valid, Cal_Sample_Time), flush=True)

    except KeyboardInterrupt:
        print("Stopped early", flush=True)

    if r0_mq2 is None or r0_mq7 is None or r0_mq135 is None:
        print("Not enough samples to calibrate. Let it run longer.")
        return

    print("Final R0 values: MQ2=%.4f MQ7=%.4f MQ135=%.4f" % (r0_mq2, r0_mq7, r0_mq135))
    if args.no_save:
        return
    save_r0(args.config, r0_mq2, r0_mq7, r0_mq135)
    print("Saved to %s. Restart the logger with:  sudo systemctl restart sensly" % args.config)


if __name__ == "__main__":
    main()
