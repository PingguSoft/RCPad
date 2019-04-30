#!/usr/bin/python
import serial
import time
import array
import os
import signal
import subprocess
import math
import struct
import RPi.GPIO as GPIO
import sys, fcntl, termios, signal
import curses, errno, re
import threading
import BatteryMonitor
import OSD
import SoftPowerSwitch
import VolWiFiMonitor

###################################################################################################
# CONSTANTS
###################################################################################################


###################################################################################################
# MAIN
###################################################################################################
_isExit = threading.Event()

def _handleSignal(signum, frame):
    _isExit.set()

def _main(portJoy, portSerial):
    signal.signal(signal.SIGINT, _handleSignal)
    signal.signal(signal.SIGTERM, _handleSignal)
    GPIO.setmode(GPIO.BCM)

    msp = BatteryMonitor.SubMSP(portSerial)
    msp.setDaemon(True)
    msp.start()

    osd = OSD.OSD()
    osd.setDaemon(True)
    osd.start()

    joystick    = VolWiFiMonitor.VolWiFiJoystick(portJoy)
    powerSwitch = SoftPowerSwitch.SoftPowerSwitch()

    while (not _isExit.isSet()):
        ts         = int(round(time.time() * 1000))
        left_msp   = msp.process(ts)
        left_stick = joystick.process(ts, osd)
        left       = min(left_msp, left_stick)

        # sleep
        if left:
            time.sleep(left / 1000.0)

    msp.stop()
    osd.stop()

if __name__ == "__main__":
    import sys

    try:
        _main(sys.argv[1], sys.argv[2])

    # Catch all other non-exit errors
    except Exception as e:
        sys.stderr.write("Unexpected exception: %s" % e)
        sys.exit(1)

    # Catch the remaining exit errors
    except:
        sys.exit(0)
