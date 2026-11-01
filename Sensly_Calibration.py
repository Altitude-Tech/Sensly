#!/usr/bin/env python3
"""Sensly HAT calibration script.

Run this with the HAT in clean air. It averages the sensor resistance over
many samples and writes the running R0 estimate for each MQ sensor to a CSV
file. Copy the final values into the R0 list at the top of Sensly.py.

Usage:
    python3 Sensly_Calibration.py              # 10 minute warm-up
    python3 Sensly_Calibration.py --warmup 0   # skip warm-up
"""

import argparse
import time

from Sensors import Sensor, reset_hat


def main():
    parser = argparse.ArgumentParser(description="Calibrate the Sensly HAT MQ sensors in clean air.")
    parser.add_argument("--warmup", type=int, default=600,
                        help="seconds to let the MQ sensors heat up before sampling (default: 600)")
    parser.add_argument("--samples", type=int, default=300,
                        help="samples per averaging window (default: 300)")
    args = parser.parse_args()

    # Reset Sensly HAT
    reset_hat(1.0)
    time.sleep(1)

    # Sensly Constants
    R0 = [0, 0, 0]
    RSAir = [9.5, 27, 3.62]
    Cal_Sample_Time = args.samples

    MQ2 = Sensor('MQ2', R0[0], RSAir[0])  # name, Calibrated R0 value, RS/R0 ratio in clean air
    MQ7 = Sensor('MQ7', R0[1], RSAir[1])
    MQ135 = Sensor('MQ135', R0[2], RSAir[2])

    datafile = time.strftime('./Sensly_Calibration_%d-%m-%Y_%H_%M_%S.csv')
    with open(datafile, 'w') as f1:
        f1.write('Time, MQ2RZero, MQ7RZero, MQ135RZero\n')
    print("Logging to %s" % datafile, flush=True)

    # Set commands for getting data from sensors
    MQ2cmd = 0x01
    MQ7cmd = 0x02
    MQ135cmd = 0x03

    # Initialise the last stored R0 value used for the running average
    L_AvRs_MQ2 = 0
    L_AvRs_MQ7 = 0
    L_AvRs_MQ135 = 0

    try:
        if args.warmup > 0:
            print("Warming up for %d minutes" % (args.warmup // 60), flush=True)
            time.sleep(args.warmup)
            print("Heating completed, calibrating (Ctrl-C to stop)", flush=True)

        while True:
            data = []
            data.append(time.strftime('%H:%M:%S'))

            AvRs_MQ2 = 0
            AvRs_MQ7 = 0
            AvRs_MQ135 = 0

            # Run calibration
            for _ in range(Cal_Sample_Time):
                AvRs_MQ2 = AvRs_MQ2 + MQ2.Get_RS(MQ2cmd)
                time.sleep(0.01)
                AvRs_MQ7 = AvRs_MQ7 + MQ7.Get_RS(MQ7cmd)
                time.sleep(0.01)
                AvRs_MQ135 = AvRs_MQ135 + MQ135.Get_RS(MQ135cmd)
                time.sleep(0.01)
            AvRs_MQ2 = AvRs_MQ2 / Cal_Sample_Time
            AvRs_MQ7 = AvRs_MQ7 / Cal_Sample_Time
            AvRs_MQ135 = AvRs_MQ135 / Cal_Sample_Time

            # Find R0 (running average with the previous estimate)
            MQ2.R0 = ((AvRs_MQ2 / MQ2.RSAIR) + L_AvRs_MQ2) / 2
            MQ7.R0 = ((AvRs_MQ7 / MQ7.RSAIR) + L_AvRs_MQ7) / 2
            MQ135.R0 = ((AvRs_MQ135 / MQ135.RSAIR) + L_AvRs_MQ135) / 2

            L_AvRs_MQ2 = MQ2.R0
            L_AvRs_MQ7 = MQ7.R0
            L_AvRs_MQ135 = MQ135.R0

            data.append(MQ2.R0)
            data.append(MQ7.R0)
            data.append(MQ135.R0)

            with open(datafile, 'a') as f2:
                f2.write(','.join(str(d) for d in data) + '\n')
            print("%s  R0: MQ2=%.1f MQ7=%.1f MQ135=%.1f" % (data[0], MQ2.R0, MQ7.R0, MQ135.R0), flush=True)

    except KeyboardInterrupt:
        print("Bye")
        print("Final R0 values -> R0 = [%.4f, %.4f, %.4f]" % (MQ2.R0, MQ7.R0, MQ135.R0))


if __name__ == "__main__":
    main()
