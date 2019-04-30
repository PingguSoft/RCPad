#!/bin/python

import RPi.GPIO as GPIO
import time
import os

PIN_POWER_KEY     = 3
PIN_POWER_DOWN    = 4
TIMEOUT_REBOOT    = 0.5
TIMEOUT_SHUTDOWN  = 3.0

class SoftPowerSwitch(object):
    def __init__(self):
        GPIO.setwarnings(False)
        GPIO.setup(PIN_POWER_KEY, GPIO.IN, pull_up_down = GPIO.PUD_UP)
        GPIO.add_event_detect(PIN_POWER_KEY, GPIO.FALLING, callback = self._checkShutdown, bouncetime = 100)

    def _checkShutdown(self, gpio):
        start = time.time()

        while time.time() < start + TIMEOUT_SHUTDOWN:
            inp = GPIO.input(gpio)
            if inp == GPIO.HIGH:
                if time.time() > start + TIMEOUT_REBOOT:
                    print("reboot !!")
                    os.system("sudo reboot")
                return
            time.sleep(0.01)

        print("shutdown now !!")

        #workaroud for RPi2
        GPIO.setup(PIN_POWER_DOWN, GPIO.IN, pull_up_down = GPIO.PUD_DOWN)
        GPIO.setup(PIN_POWER_DOWN, GPIO.OUT)
        GPIO.output(PIN_POWER_DOWN, 1)
        #
        os.system("sudo shutdown -h now")


###################################################################################################
# MAIN
###################################################################################################
if __name__ == "__main__":
    import sys

    try:
        GPIO.setmode(GPIO.BCM)
        powerSwitch = SoftPowerSwitch()
        while True:
            #GPIO.wait_for_edge(PIN_POWER_KEY, GPIO.FALLING)
            #checkShutdown(PIN_POWER_KEY)
            time.sleep(60)

    # Catch all other non-exit errors
    except Exception as e:
        sys.stderr.write("Unexpected exception: %s" % e)
        sys.exit(1)

    # Catch the remaining exit errors
    except:
        sys.exit(0)
