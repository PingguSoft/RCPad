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

from serial import Serial
from threading import Event
from time import sleep, time
import threading
import struct

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

###################################################################################################
# CONVERSION FUNCTIONS
###################################################################################################
    def __init__(self, serial):
        threading.Thread.__init__(self)
        self._port = serial
        self._exitNow = Event()
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
                sleep(0.1)
                
        print("MSP thread finished")

    def _stop(self):
        self._exitNow.set()
        self.join()

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
            startTime = time()
            while True:
                if self._responses[command].finished:
                    return True
                if (time() - startTime > self.responseTimeout):
                    return False
                sleep(0)
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
