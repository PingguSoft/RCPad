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

from pyudev import Context
from threading import Event
from MSP import MSP
from OSD import OSD

###################################################################################################
# CONSTANTS
###################################################################################################
APP_PATH      = "."
RATE_RESCAN_MS= 2000
RATE_BATT_MS  = 1000
RATE_EVENT_MS = 50

R1            = 10000
R2            =  5100
VOLT_CHARGING = 8.45
VOLT_100      = 4.1  * 2
VOLT_75       = 3.76 * 2
VOLT_50       = 3.63 * 2
VOLT_25       = 3.5  * 2
VOLT_0        = 3.2  * 2

class COMMANDS:
    NOP              = 0x00
    GET_BATTERY_ADC  = 0x01


###################################################################################################
# GLOBAL VARIABLES
###################################################################################################
isExit        = Event()

###################################################################################################
# Subclassing from MSP
###################################################################################################
def volt2adc(volt):
    vout = R2 / (R1 + R2) * volt
    adc  = vout / 5 * 1024
    return adc
    
def adc2volt(adc):
    vout = adc * 5.0 / 1024.0
    volt = vout * (R1 + R2) / R2
    return volt

class SubMSP(MSP):
    def __init__(self, serial):
        super(SubMSP, self).__init__(serial)
        self._tblCommand = {
            0x00 : self._nop,
            0x01 : self._handleBattery
        }
        self._curPercent = ""
        self._procOSD    = None
        self._listVolts  = []
        self._isCharging = False
        
    def stop(self):
        super(SubMSP, self).stop()
        if self._procOSD != None:
            self._procOSD.terminate()
            self._procOSD.wait()
            self._procOSD = None
            #print "kill pid:%d" % self._procOSD.pid

    def _nop(self, data):
        print "_nop "
        #print ("{0}".format(", ".join("{:02X}".format(c) for c in data)))


    def _showIcon(self, percent):
        if self._curPercent != percent:
            if self._procOSD != None:
                self._procOSD.terminate()
                self._procOSD.wait()
                print "kill pid:%d" % self._procOSD.pid
                self._procOSD = None
                
            self._curPercent = percent
            self._procOSD = subprocess.Popen([APP_PATH + "/pngview", "-b0x0000", "-l30000", "-n", "-x768", "-y2",
                APP_PATH + "/battery_" + percent + ".png"])
                
#            self._procOSD = subprocess.Popen([APP_PATH + "/pngview", "-b0x0000", "-l30000", "-t1000",
#                APP_PATH + "/volume0.png"])
                
            #print "%d" % self._procOSD.pid
       
    def _handleBattery(self, data):
        adc  = self.toUInt16(data);
        volt = adc2volt(adc);

        # first check charging status change
        if volt > VOLT_CHARGING:
            self._isCharging = True
        elif self._isCharging == True:
            del self._listVolts[:]
            self._isCharging = False
            
        # append volt to 20 sec window
        if len(self._listVolts) >= 20:
            self._listVolts.pop(0)
        self._listVolts.append(volt)
        
        # get avg volt
        sum = 0
        for v in self._listVolts:
            sum = sum + v
        avg = sum / len(self._listVolts)

        #print "battery => %d %fV (%d) => %fV" % (adc, volt, len(self._listVolts), avg)

        if self._isCharging == True:
            self._showIcon("charging")
        elif avg > VOLT_100:
            self._showIcon("100")
        elif avg > VOLT_75:
            self._showIcon("75")
        elif avg > VOLT_50:
            self._showIcon("50")
        elif avg > VOLT_25:
            self._showIcon("25")
        else:
            self._showIcon("0")

    def commandRecceived(self, command, data, error=False):
        result = self._tblCommand.get(command, self._nop)
        if result:
            result(data)


###################################################################################################
# VOLUME WIFI MANAGER CLASS
###################################################################################################
class VolWiFiManager(object):
    def __init__(self):
        self._procOSD  = None        
        self._curVol   = int(self._getCmdResult("amixer get PCM|grep -o [0-9]*%|sed 's/%//'"))
        self._curWiFi  = self._getCmdResult("cat /sys/class/net/wlan0/operstate")       # up or down

    def _getCmdResult(self, cmd):
        p = subprocess.Popen(cmd, shell = True, stdout = subprocess.PIPE)
        output = p.communicate()[0]
        return output

    def _dispVolume(self, vol):
        if self._procOSD != None:
            self._procOSD.terminate()
            self._procOSD.wait()

        self._procOSD = subprocess.Popen([APP_PATH + "/pngview", "-b0x0000", "-l30000", "-n", "-t1000", 
            APP_PATH + "/volume" + str(vol / 6) + ".png"])

    def _dispWiFi(self, state):
        if self._procOSD != None:
            self._procOSD.terminate()
            self._procOSD.wait()

        self._procOSD = subprocess.Popen([APP_PATH + "/pngview", "-b0x0000", "-l30000", "-n", "-t1000",
            APP_PATH + "wifi-" + ("on" if state == "up" else "off") + ".png"])
                
    def incVolume(self):
        if self._curVol < 95:
            self._curVol += 6
            self._getCmdResult("amixer set PCM -- " + str(self._curVol) + "%")
        self._dispVolume(self._curVol)

    def decVolume(self):
        if self._curVol > 5:
            self._curVol -= 6
            self._getCmdResult("amixer set PCM -- " + str(self._curVol) + "%")
        self._dispVolume(self._curVol)
            
    def toggleWiFi(self):
        if self._curWiFi == "up":
            self._getCmdResult("sudo ifconfig wlan0 down")
            self._curWiFi = "down"
        else:
            self._getCmdResult("sudo ifconfig wlan0 up")
            self._curWiFi = "up"
        self._dispWiFi(self._curWiFi)


###################################################################################################
# JOYSTICK EVENTS HANDLING
###################################################################################################
class Joystick(object):
    def __init__(self, dev):
        self._dev = dev
        self._devs = []
        self._fds  = []
        self._js_last = []
        self._lastScanTS = 0;
        self._event_format  = 'IhBB'
        self._event_size    = struct.calcsize(self._event_format)
        
        self.JS_EVENT_BUTTON = 0x01
        self.JS_EVENT_AXIS   = 0x02
        self.JS_EVENT_INIT   = 0x80
        self.JS_REP          = 0.20
        

    def _get_devices(self):
        devs = []
        if self._dev == '/dev/input/jsX':
            for dev in os.listdir('/dev/input'):
                if dev.startswith('js'):
                    devs.append('/dev/input/' + dev)
        else:
            devs.append(self._dev)

        return devs

    def _open_devices(self):
        devs = self._get_devices()

        fds = []
        for dev in devs:
            try:
                fds.append(os.open(dev, os.O_RDONLY | os.O_NONBLOCK ))
            except:
                pass

        return devs, fds

    def _close_fds(self, fds):
        for fd in fds:
            os.close(fd)

    def _read_event(self, fd):
        while True:
            try:
                event = os.read(fd, self._event_size)
            except OSError, e:
                if e.errno == errno.EWOULDBLOCK:
                    return None
                return False
            else:
                return event

    def _process_event(self, event, osd, manager):
        (js_time, js_value, js_type, js_number) = struct.unpack(self._event_format, event)

        # ignore init events
        if js_type & self.JS_EVENT_INIT:
            return False

        #print "type " + str(js_type) + " num " + str(js_number) + " val " + str(js_value)

        if js_type == self.JS_EVENT_BUTTON and js_value == 1:
            if js_number == 16:
                manager.decVolume()
            elif js_number == 17:
                manager.incVolume()
            elif js_number == 19:
                manager.toggleWiFi()
            # OSD dedicated buttons
            elif js_number == 20:
                osd.queue('U')
            elif js_number == 21:
                osd.queue('M')
            elif js_number == 22:
                osd.queue('D')
            elif js_number == 23:
                osd.queue('R')
            elif js_number == 24:
                osd.queue('O')

        return True

    def process(self, ts, osd, manager):
        do_sleep = True
        
        if not self._fds:
            self._devs, self._fds = self._open_devices()
            if self._fds:
                i = 0
                self._js_last = [None] * len(self._fds)
                for js in self._fds:
                    self._js_last[i] = ts
                    i += 1
        else:
            i = 0
            for fd in self._fds:
                event = self._read_event(fd)
                if event:
                    do_sleep = False
                    if ts - self._js_last[i] > RATE_EVENT_MS:
                        if self._process_event(event, osd, manager):
                            self._js_last[i] = ts
                elif event == False:
                    self._close_fds(self._fds)
                    self._fds = []
                    break
                i += 1


        # check if new devices are attached every 2sec
        if ts - self._lastScanTS > RATE_RESCAN_MS:
            self._lastScanTS = ts
            if cmp(self._devs, self._get_devices()):
                self._close_fds(self._fds)
                self._fds = []        

        return do_sleep


###################################################################################################
# MAIN
###################################################################################################
def handleSignal(signum, frame):
    isExit.set()

def main():
    signal.signal(signal.SIGINT, handleSignal)
    signal.signal(signal.SIGTERM, handleSignal)
    GPIO.setmode(GPIO.BCM)

    lastBattTS = 0

    port = serial.Serial(sys.argv[2], 115200, writeTimeout = 0.1)
    msp = SubMSP(port)
    msp.setDaemon(True)
    msp.start()

    osd = OSD()
    osd.setDaemon(True)
    osd.start()
    
    joystick = Joystick(sys.argv[1])
    manager  = VolWiFiManager()
   
    do_sleep = True
    while (not isExit.isSet()):
        ts       = int(round(time.time() * 1000))
        do_sleep = joystick.process(ts, osd, manager)

        # probe battery level
        if ts - lastBattTS > RATE_BATT_MS:
            msp.sendCommand(COMMANDS.GET_BATTERY_ADC)
            lastBattTS = ts

        # sleep
        if do_sleep:
            time.sleep(RATE_EVENT_MS / 1000.0)

    msp.stop()
    port.close()
    osd.stop()

if __name__ == "__main__":
    import sys

    try:
        main()

    # Catch all other non-exit errors
    except Exception as e:
        sys.stderr.write("Unexpected exception: %s" % e)
        sys.exit(1)

    # Catch the remaining exit errors
    except:
        sys.exit(0)
