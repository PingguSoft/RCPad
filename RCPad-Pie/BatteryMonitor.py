#Python MSP Serial Protocol communication library for radio-controlled devices
#Copyright (C) 2015 Jonathan Dean
#This program is free software: you can redistribute it and/or modify
#it under the terms of the GNU General Public License as published by
#the Free Software Foundation, either version 3 of the License, or
#(at your option) any later version.

#This program is distributed in the hope that it will be useful,
#but WITHOUT ANY WARRANTY; without even the implied warranty of
#MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#GNU General Public License for more details.

#You should have received a copy of the GNU General Public License
#along with this program.  If not, see <http://www.gnu.org/licenses/>.

import serial
import threading
import struct
import signal
import subprocess
import time
import array
import os
import signal
import subprocess
import math

###################################################################################################
# CONSTANTS
###################################################################################################
APP_PATH      = os.path.dirname(os.path.abspath(__file__))

# BATTERY CONFIGURATION
RATE_BATT_MS  = 2000
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
# MSP CLASS
###################################################################################################
class MSP(threading.Thread):
    class _MSPSTATES:
        """Enum of MSP States"""
        IDLE         = 0
        HEADER_START = 1
        HEADER_M     = 2
        HEADER_ARROW = 3
        HEADER_SIZE  = 4
        HEADER_CMD   = 5

    class _MSPResponse:
        """Combine MSP response data and finished communication flag"""
        def __init__(self):
            self.finished = False
            self.data = []

    def __init__(self, serial):
        threading.Thread.__init__(self)
        self._port = serial
        self._exitNow = threading.Event()
        self._responses = {}
        self.responseTimeout = 3

    def run(self):
        state        = self._MSPSTATES.IDLE
        data         = bytearray()
        dataSize     = 0
        dataChecksum = 0
        command      = 0

        while (not self._exitNow.isSet()):
            if (self._port.inWaiting() > 0):
                inByte = ord(self._port.read())
                if (state == self._MSPSTATES.IDLE):
                    state = self._MSPSTATES.HEADER_START if (inByte==36) else self._MSPSTATES.IDLE #chr(36)=='$'
                elif (state == self._MSPSTATES.HEADER_START):
                    state = self._MSPSTATES.HEADER_M if (inByte==77) else self._MSPSTATES.IDLE #chr(77)=='M'
                elif (state == self._MSPSTATES.HEADER_M):
                    state = self._MSPSTATES.HEADER_ARROW if (inByte==62) else self._MSPSTATES.IDLE #chr(62)=='>'
                elif (state == self._MSPSTATES.HEADER_ARROW):
                    dataSize = inByte
                    data = bytearray()
                    dataChecksum = inByte
                    state = self._MSPSTATES.HEADER_SIZE
                elif (state == self._MSPSTATES.HEADER_SIZE):
                    command = inByte
                    dataChecksum = (dataChecksum ^ inByte)
                    state = self._MSPSTATES.HEADER_CMD
                elif (state == self._MSPSTATES.HEADER_CMD) and (len(data) < dataSize):
                    data.append(inByte)
                    dataChecksum = (dataChecksum ^ inByte)
                elif (state == self._MSPSTATES.HEADER_CMD) and (len(data) >= dataSize):
                    if (dataChecksum == inByte):
                        #Good command, do something with it
                        #self._processCommand(command, data)
                        self.commandRecceived(command, data) #Call the subclass method
                    else:
                        #Bad checksum
                        pass
                    state = self._MSPSTATES.IDLE
            else:
                time.sleep(0.1)

        print("MSP thread finished")

    def _stop(self):
        self._exitNow.set()
        self.join()
        self._port.close()

    def __del__(self):
        self._stop()

    def stop(self):
        self._stop()


###################################################################################################
# CONVERSION FUNCTIONS
###################################################################################################
    def toInt16(self, data):
        if (len(data) == 2):
            return struct.unpack("@h", struct.pack("<BB", data[0], data[1]))[0]
        else:
            return None

    def toUInt16(self, data):
        if (len(data) == 2):
            return struct.unpack("@H", struct.pack("<BB", data[0], data[1]))[0]
        else:
            return None

    def toInt32(self, data):
        if (len(data) == 4):
            return struct.unpack("@i", struct.pack("<BBBB", data[0], data[1], data[2], data[3]))[0]
        else:
            return None

    def toUInt32(self, data):
        if (len(data) == 4):
            return struct.unpack("@I", struct.pack("<BBBB", data[0], data[1], data[2], data[3]))[0]
        else:
            return None

    def fromInt16(self, value):
        return struct.unpack("<BB", struct.pack("@h", value))

    def fromUInt16(self, value):
        return struct.unpack("<BB", struct.pack("@H", value))

    def fromInt32(self, value):
        return struct.unpack("<BBBB", struct.pack("@i", value))

    def fromUInt32(self, value):
        return struct.unpack("<BBBB", struct.pack("@I", value))

    def _processCommand(self, command, data):
        if (self._responses.has_key(command)):
            self._responses[command].data = data
            self._responses[command].finished = True
            self.commandRecceived(command, data) #Call the subclass method
            return True
        else:
            return False

    def sendCommand(self, command, data=None):
        if (data is None):
            dataSize = 0
        else:
            if len(data) < 256:
                dataSize = len(data)
            else:
                return False
        output = bytearray()
        output.append('$')
        output.append('M')
        output.append('<')
        output.append(dataSize)
        checksum = dataSize
        output.append(command)
        checksum = (checksum ^ command)
        if (dataSize > 0):
            for b in data:
                output.append(b)
                checksum = (checksum ^ b)
        output.append(checksum)
        try:
            size = self._port.write(output)
            self._responses.update({command: self._MSPResponse()})
        except Exception, e:
            print "serial port write error: " + str(e)
            return False
        return True

    def _waitForResponse(self, command):
        if (self._responses.has_key(command)):
            startTime = time.time()
            while True:
                if self._responses[command].finished:
                    return True
                if (time.time() - startTime > self.responseTimeout):
                    return False
                time.sleep(0)
        else:
            return False

    def _sendAndWait(self, command, data=None):
        if (self._sendCommand(command, data)):
            return self._waitForResponse(command)
        else:
            return False

    def _sendAndGet(self, command, expectedSize=None):
        if self._sendAndWait(command):
            rdata = self._responses[command].data
            del self._responses[command]
            if (expectedSize is not None):
                if (len(rdata) == expectedSize):
                    return rdata
                else:
                    return None
            else:
                return rdata
        else:
            return None

    def commandRecceived(self, command, data, error=False):
        """Process a received command from the device
        Args:
            command (int): the MSP command number
            data (bytearray): the data associated with the command
            error (bool): True if the command is reporting an error, False normally
        Returns:
            None
        Notes:
            This method is intended for subclasses of MSP to be able to monitor and
            process incoming data from the device.
        """
        pass


###################################################################################################
# Subclassing from MSP
###################################################################################################
class SubMSP(MSP):
    def __init__(self, port):
        super(SubMSP, self).__init__(serial.Serial(port, 115200, writeTimeout = 0.1))
        self._tblCommand = {
            0x00 : self._nop,
            0x01 : self._handleBattery
        }
        self._curPercent = ""
        self._procOSD    = None
        self._listVolts  = []
        self._isCharging = False
        self._lastBattTS = 0

    def stop(self):
        super(SubMSP, self).stop()
        if self._procOSD != None:
            self._procOSD.terminate()
            self._procOSD.wait()
            self._procOSD = None
            #print "kill pid:%d" % self._procOSD.pid


    def _volt2adc(self, volt):
        vout = R2 / (R1 + R2) * volt
        adc  = vout / 5 * 1024
        return adc

    def _adc2volt(self, adc):
        vout = adc * 5.0 / 1024.0
        volt = vout * (R1 + R2) / R2
        return volt

    def _nop(self, data):
        pass
        #print "_nop "
        #print ("{0}".format(", ".join("{:02X}".format(c) for c in data)))


    def _dispBattery(self, percent):
        if self._curPercent != percent:
            if self._procOSD != None:
                self._procOSD.terminate()
                self._procOSD.wait()
                #print "kill pid:%d" % self._procOSD.pid
                self._procOSD = None

            self._curPercent = percent
            self._procOSD = subprocess.Popen([APP_PATH + "/pngview", "-b0x0000", "-l30000", "-n", "-x768", "-y2",
                APP_PATH + "/battery_" + percent + ".png"])

            #print "%d" % self._procOSD.pid

    def _handleBattery(self, data):
        adc  = self.toUInt16(data);
        volt = self._adc2volt(adc);

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
            self._dispBattery("charging")
        elif avg > VOLT_100:
            self._dispBattery("100")
        elif avg > VOLT_75:
            self._dispBattery("75")
        elif avg > VOLT_50:
            self._dispBattery("50")
        elif avg > VOLT_25:
            self._dispBattery("25")
        else:
            self._dispBattery("0")

    def commandRecceived(self, command, data, error=False):
        result = self._tblCommand.get(command, self._nop)
        if result:
            result(data)

    def process(self, ts):
        # probe battery level
        if ts - self._lastBattTS > RATE_BATT_MS:
            self.sendCommand(COMMANDS.GET_BATTERY_ADC)
            self._lastBattTS = ts
            left = 0
        else:
            left = RATE_BATT_MS - (ts - self._lastBattTS)
        return left


###################################################################################################
# MAIN
###################################################################################################
_isExit = threading.Event()

def _handleSignal(signum, frame):
    _isExit.set()

def _main(serialPort):
    signal.signal(signal.SIGINT, _handleSignal)
    signal.signal(signal.SIGTERM, _handleSignal)

    msp = SubMSP(serialPort)
    msp.setDaemon(True)
    msp.start()

    while (not _isExit.isSet()):
        ts   = int(round(time.time() * 1000))
        left = msp.process(ts);
        if left > 0:
            time.sleep(left / 1000)

    msp.stop()

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