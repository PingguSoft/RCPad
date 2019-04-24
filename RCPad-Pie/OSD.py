import Queue
import threading
from time import sleep
import RPi.GPIO as GPIO

###################################################################################################
# CONSTANTS
###################################################################################################
PIN_LCD_ON_OFF = 26
PIN_RETURN     = 19
PIN_MENU       = 16
PIN_UP         = 20
PIN_DOWN       = 21


class OSD(threading.Thread):
    def __init__(self):
        threading.Thread.__init__(self)
        self._dataQueue = Queue.Queue()

    def _toggle(self, pin):
        GPIO.setup(pin, GPIO.IN)
        sleep(0.1)
        GPIO.setup(pin, GPIO.OUT)
        GPIO.output(pin, 0);
        sleep(0.1)
        GPIO.setup(pin, GPIO.IN)

    def run(self): 
        while True:	
            data = self._dataQueue.get()	
            print("data : " + str(data))
            self._dataQueue.task_done()
            if data == 'Q':
                break
            elif data == 'R':
                self._toggle(PIN_RETURN)
            elif data == 'M':
                self._toggle(PIN_MENU)
            elif data == 'U':
                self._toggle(PIN_UP)
            elif data == 'D':
                self._toggle(PIN_DOWN)
            elif data == 'O':
                self._toggle(PIN_LCD_ON_OFF)
                
        print("OSD thread finished")

    def queue(self, data):
        self._dataQueue.put(data)
        
    def stop(self):
        self._dataQueue.put('Q')
        self.join()

###################################################################################################
# 
###################################################################################################