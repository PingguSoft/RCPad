import Queue
import threading
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
        GPIO.setup(PIN_LCD_ON_OFF, GPIO.IN)
        GPIO.setup(PIN_RETURN,     GPIO.IN)
        GPIO.setup(PIN_MENU,       GPIO.IN)
        GPIO.setup(PIN_UP,         GPIO.IN)
        GPIO.setup(PIN_DOWN,       GPIO.IN)

    def _toggle(self, pin):
        GPIO.setup(pin, GPIO.IN)
        time.sleep(0.1)
        GPIO.setup(pin, GPIO.OUT, initial=GPIO.LOW)
        time.sleep(0.1)
        GPIO.setup(pin, GPIO.IN)

    def run(self): 
        while True:	
            data = self._dataQueue.get()	
            #print("data : " + str(data))
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
# MAIN
###################################################################################################
if __name__ == "__main__":
    import sys
    
    try:
        GPIO.setmode(GPIO.BCM)
        osd = OSD()
        osd.start()
        while True:
            key = raw_input('M:menu, R:return, U:up, D:down, O:lcd_on_off, Q:quit : ')
            osd.queue(key)
            if key == 'Q':
                break

    # Catch all other non-exit errors
    except Exception as e:
        sys.stderr.write("Unexpected exception: %s" % e)
        sys.exit(1)

    # Catch the remaining exit errors
    except:
        sys.exit(0)

    osd.stop()
    GPIO.cleanup()