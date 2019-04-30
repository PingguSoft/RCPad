import time
import array
import os
import subprocess
import math
import struct
import sys, fcntl, termios, signal
import curses, errno, re
import threading

###################################################################################################
# CONSTANTS
###################################################################################################
APP_PATH      = os.path.dirname(os.path.abspath(__file__))
RATE_RESCAN_MS= 2000
RATE_EVENT_MS = 50

###################################################################################################
# VOLUME WIFI MANAGER CLASS
###################################################################################################
class VolWiFiManager(object):
    def __init__(self):
        self._procOSD  = None
        self._curVol   = int(self._getCmdResult("amixer get PCM|grep -o [0-9]*%|sed 's/%//'"))
        self._curWiFi  = self._getCmdResult("cat /sys/class/net/wlan0/operstate")       # up or down
        self._curWiFi  = self._curWiFi.strip().lower()
        #print self._curWiFi

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
            APP_PATH + "/wifi-" + ("on" if state == "up" else "off") + ".png"])

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
class VolWiFiJoystick(object):
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

        self._manager        = VolWiFiManager()

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

    def _process_event(self, event, osd):
        (js_time, js_value, js_type, js_number) = struct.unpack(self._event_format, event)

        # ignore init events
        if js_type & self.JS_EVENT_INIT:
            return False

        #print "type " + str(js_type) + " num " + str(js_number) + " val " + str(js_value)

        if js_type == self.JS_EVENT_BUTTON and js_value == 1:
            if self._manager != None:
                if js_number == 16:
                    self._manager.decVolume()
                elif js_number == 17:
                    self._manager.incVolume()
                elif js_number == 19:
                    self._manager.toggleWiFi()

            # OSD dedicated buttons
            if osd != None:
                if js_number == 20:
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

    def process(self, ts, osd):
        left = RATE_EVENT_MS

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
                    left = 0
                    if ts - self._js_last[i] > RATE_EVENT_MS:
                        if self._process_event(event, osd):
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

        return left

###################################################################################################
# MAIN
###################################################################################################
_isExit = threading.Event()

def _handleSignal(signum, frame):
    _isExit.set()

def _main(joyPort):
    signal.signal(signal.SIGINT, _handleSignal)
    signal.signal(signal.SIGTERM, _handleSignal)

    joystick = VolWiFiJoystick(joyPort)

    do_sleep = True
    while (not _isExit.isSet()):
        ts   = int(round(time.time() * 1000))
        left = joystick.process(ts, None)

        # sleep
        if left > 0:
            time.sleep(left / 1000.0)

if __name__ == "__main__":
    import sys

    try:
        _main(sys.argv[1])

    # Catch all other non-exit errors
    except Exception as e:
        sys.stderr.write("Unexpected exception: %s" % e)
        sys.exit(1)

    # Catch the remaining exit errors
    except:
        sys.exit(0)

