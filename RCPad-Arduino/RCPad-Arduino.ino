#include <avr/wdt.h>
#include <Joystick.h>
#include <EEPROM.h>
#include "Keyboard.h"
#include "Mouse.h"
#include "common.h"
#include "MSP.h"

/*
*****************************************************************************************
* CONSTANTS
*****************************************************************************************
*/
//#define DEBUG

#define MAGIC_ID                0xcafebabe
#define ANALOG_RETRY_COUNT      5

// timeouts (ms)
#define TIMEOUT_SHIFT_MCLICKS   300
#define TIMEOUT_STICK_REPORT    5
#define TIMEOUT_BATTERY_REPORT  1000

// PINS
// analog axis
#define PIN_A_AXIS_LEFT_X       A0
#define PIN_A_AXIS_LEFT_Y       A1
#define PIN_A_AXIS_RIGHT_X      A2
#define PIN_A_AXIS_RIGHT_Y      A3

#define PIN_A_AXIS_HAT_X        A10
#define PIN_A_AXIS_HAT_Y        A9
#define PIN_A_BATTERY_SENSE     A8

// left side buttons
#define PIN_BTN_LTHUMB          15
#define PIN_BTN_SHIFT           PIN_BTN_LTHUMB
#define PIN_BTN_L1              6
#define PIN_BTN_L2              16
#define PIN_BTN_START           1

// right side
//#define PIN_BTN_RTHUMB         7
#define PIN_BTN_R1              5
#define PIN_BTN_R2              14
#define PIN_BTN_A               4
#define PIN_BTN_B               3
#define PIN_BTN_X               2
#define PIN_BTN_Y               0
#define PIN_BTN_SELECT          7

#define BTN_HW_CNTS             (sizeof(TBL_PIN_BUTTONS) - 1)   // 10 (shift key excluded)
#define BTN_ONLY_CNTS           (BTN_HW_CNTS * 2)               // 20
#define BTN_STATE_CNTS          (BTN_ONLY_CNTS + 1)             // 21 (shift key included)
#define BTN_REPORT_CNTS         (BTN_HW_CNTS * 2 + 5)           // 26 (4 osd keys + lcd on/off included)

// hatState buttons
#define HAT_CNTS                1
#define HAT_ADC_NO_KEY         (1023 * 0.8)
#define HAT_ADC_RIGHT_UP       (1023 * 0.65)
#define HAT_ADC_RIGHT_DOWN     (1023 * 0.40)
// 1 ADC pin for exclusive buttons
//
// Vcc     Ain
//  |      |
//  +--R1--+
//  R2     |
//  +-- \--+  up     N = 2 switches
//  R2     |
//  +-- \--+  down
//  R2
//  |
//  =
//
// n   = 1 ~ N
// Rhi = (R1 * n * R2) / (R1 + n * R2)
// Rlo = ((N + 1) - n) * R2
// Vout = Vcc * (Rlo / (Rhi + Rlo))
//

#define HAT_NONE               0
#define HAT_UP                 1
#define HAT_RIGHT              2
#define HAT_DOWN               4
#define HAT_LEFT               8
//        1
//    9   |   3
//        |
//  8 ----0----  2
//        |
//   12   |   6
//        4



/*
*****************************************************************************************
* MACROS
*****************************************************************************************
*/
#define ABS(a)                  (((a) >= 0)? (a) : -(a))
#define MIN(a, b)               (((a) <= (b))? (a) : (b))
#define MAX(a, b)               (((a) >= (b))? (a) : (b))


/*
*****************************************************************************************
* TYPES
*****************************************************************************************
*/
struct axis_range {
    u16     minX, maxX;
    u16     minY, maxY;
};

struct cal_info {
    u32                 dwMagicID;
    struct axis_range   left;
    struct axis_range   right;
};

// Packet
enum pad_cmd {
    CMD_NONE = 0,
    CMD_BATTERY,
};

enum pad_mode {
    MODE_KEYBOARD = 0,
    MODE_MOUSE,
    MODE_JOYSTICK,
    MODE_OSD,
};

class SubMSP;


/*
*****************************************************************************************
* CONSTANT TABLES
*****************************************************************************************
*/
static const u8 PROGMEM TBL_PIN_BUTTONS[] = {
    PIN_BTN_SHIFT,
    PIN_BTN_A,   PIN_BTN_B,   PIN_BTN_X,   PIN_BTN_Y,      PIN_BTN_L1,
    PIN_BTN_R1,  PIN_BTN_L2,  PIN_BTN_R2,  PIN_BTN_SELECT, PIN_BTN_START,
};

static const u8 PROGMEM TBL_PIN_ANALOG[] = {
    PIN_A_AXIS_LEFT_X,  PIN_A_AXIS_LEFT_Y,
    PIN_A_AXIS_RIGHT_X, PIN_A_AXIS_RIGHT_Y,
    PIN_A_AXIS_HAT_X,   PIN_A_AXIS_HAT_Y,
    PIN_A_BATTERY_SENSE
};

static const s16 PROGMEM TBL_ANGLES[] = {
     -1,   0,  90,  45,
    180,  -1, 135,  -1,
    270, 315,  -1,  -1,
    225
};

static const u8 PROGMEM TBL_MAP_HAT_KEY[] = {
    HAT_UP,    KEY_UP_ARROW,
    HAT_DOWN,  KEY_DOWN_ARROW,
    HAT_LEFT,  KEY_LEFT_ARROW,
    HAT_RIGHT, KEY_RIGHT_ARROW
};

static const u8 PROGMEM TBL_MAP_BTN_KEY[] = {
    KEY_RETURN,     // A
    KEY_ESC,        // B
    KEY_BACKSPACE,  // X
    KEY_TAB,        // Y
    KEY_LEFT_SHIFT, // L1
    KEY_RIGHT_SHIFT,// R1
    KEY_LEFT_CTRL,  // L2
    KEY_RIGHT_CTRL, // R2
    KEY_ESC,        // SELECT
    KEY_RETURN,     // START

    '1',            // SHIFT + A
    '2',            // SHIFT + B
    '3',            // SHIFT + X
    '4',            // SHIFT + Y
    '5',            // SHIFT + L1
    '6',            // SHIFT + R1
    '7',            // SHIFT + L2
    '8',            // SHIFT + R2
    '9',            // SHIFT + SELECT
    '0',            // SHIFT + START
};

static const u8 PROGMEM TBL_MAP_BTN_MOUSE[] = {
    MOUSE_LEFT,     // A
    MOUSE_RIGHT,    // B
    MOUSE_MIDDLE,   // X
};


/*
*****************************************************************************************
* VARIABLES
*****************************************************************************************
*/
static struct cal_info  mCalInfo;
static u8               mLastBtnState[BTN_STATE_CNTS];
static bool             mIsCalMode     = false;
static long             mFirstShiftOnlyTS = 0;
static u8               mShiftOnlyCtr  = 0;
static u8               mLastHatState  = HAT_NONE;
static long             mLastStickTS   = 0;
static enum pad_mode    mPadMode;
static Joystick_        *mJoyStick = NULL;
static SubMSP           *mMSP;
static u16              mLastLX, mLastLY;
static u16              mLastRX, mLastRY;
static u32              mResetFlag __attribute__ ((section(".noinit")));

/*
*****************************************************************************************
* FUNCTIONS
*****************************************************************************************
*/
u16 analogReadAvg(s16 pin) {
    u16 v;
    u32 sum = 0;
    u16 values[ANALOG_RETRY_COUNT];

    for (u8 i = 0; i < ANALOG_RETRY_COUNT; i++) {
        v = analogRead(pin);
        values[i] = v;
        sum += v;
    }

    u16 avg = sum / ANALOG_RETRY_COUNT;
    u8  cnt = ANALOG_RETRY_COUNT;
    for (u8 i = 0; i < ANALOG_RETRY_COUNT; i++) {
        v = values[i];
        if (ABS(v - avg) > 100) {
            sum -= v;
            cnt --;
        }
    }
    return (cnt > 0) ? (sum / cnt) : 0;
}

void printf(const __FlashStringHelper *fmt, ...) {
#ifdef DEBUG    
    char    buf[128];
    va_list args;

    va_start (args, fmt);

#ifdef __AVR__
    vsnprintf_P(buf, sizeof(buf), (const char *)fmt, args); // progmem for AVR
#else
    vsnprintf(buf, sizeof(buf), (const char *)fmt, args); // for the rest of the world
#endif
    va_end(args);

    Serial.print(buf);
#endif
}

void printf(char *fmt, ...) {
#ifdef DEBUG
    char    buf[128];
    va_list args;

    va_start (args, fmt);
    vsnprintf(buf, sizeof(buf), fmt, args);
    va_end(args);

    Serial.print(buf);
#endif
}

void setAxisRange(struct cal_info *info) {
    if (mJoyStick != NULL && info != NULL) {
        mJoyStick->setXAxisRange(info->left.minX, info->left.maxX);
        mJoyStick->setYAxisRange(info->left.minY, info->left.maxY);
        mJoyStick->setZAxisRange(info->right.minX, info->right.maxX);
        mJoyStick->setRzAxisRange(info->right.minY, info->right.maxY);
    }
}


#define MOUSE_MOVE_RANGE        12
#define MOUSE_MOVE_THRESHOLD    2

s16 getMouseMove(u16 v, u16 min, u16 max, u8 slow) {
    s16 center = (max + min) / 2;
    s16 range = slow ? 5 : MOUSE_MOVE_RANGE;
    s16 dist;

    dist = v - center;
    dist = map(dist, -center, center, -range, range);

    if (ABS(dist) < MOUSE_MOVE_THRESHOLD) {
        dist = 0;
    }

    return dist;
}


/*
*****************************************************************************************
* SubMSP HANDLER
*****************************************************************************************
*/
class SubMSP : public MSP 
{
    public:
        SubMSP(Serial_ *serial):MSP(serial) { }
    
        virtual s8 onReceived(u8 cmd, u8 *data, u8 size, u8 *res) {
            s8 ret = -1;

            switch (cmd) {
                case CMD_BATTERY:
                    *((u16*)res) = analogReadAvg(PIN_A_BATTERY_SENSE);
                    ret = 2;
                    break;
            }

            return ret;
        }
};


void setup() {
    wdt_disable();
    for (u8 i = 0; i < sizeof(TBL_PIN_BUTTONS); i++) {
        pinMode(pgm_read_byte(&TBL_PIN_BUTTONS[i]), INPUT_PULLUP);
        mLastBtnState[i] = 0;
    }

    for (u8 i = 0; i < sizeof(TBL_PIN_ANALOG); i++) {
        pinMode(pgm_read_byte(&TBL_PIN_ANALOG[i]), INPUT);
    }

    EEPROM.get(0, mCalInfo);
    if (mCalInfo.dwMagicID != MAGIC_ID) {
        mCalInfo.left.minX = 230;
        mCalInfo.left.maxX = 840;
        mCalInfo.left.minY = 230;
        mCalInfo.left.maxY = 840;
        mCalInfo.right= mCalInfo.left;
    }

#ifdef FEATURE_KEYBOARD
    Keyboard.begin();
    mPadMode = MODE_KEYBOARD;
#else
    Mouse.begin();
    mPadMode = MODE_MOUSE;
#endif

    if (mResetFlag == MAGIC_ID || mPadMode == MODE_MOUSE) {
        mJoyStick = new Joystick_(JOYSTICK_DEFAULT_REPORT_ID,JOYSTICK_TYPE_GAMEPAD,
                      BTN_REPORT_CNTS, HAT_CNTS,    // Button Count, Hat Switch Count
                      true,  true,  true,           // X and Y, Z Axis
                      false, false, true,           // Rx, Ry, or Rz
                      false, false,                 // rudder or throttle
                      false, false, false);         // accelerator, brake, or steering
        mJoyStick->begin();
        setAxisRange(&mCalInfo);
        if (mResetFlag == MAGIC_ID) {
            mPadMode = MODE_JOYSTICK;
            mResetFlag = 0;
        }
    }
    
    Serial.begin(115200);
    mMSP = new SubMSP(&Serial);
}

u8 getHatIndex(u8 hatState) {
    for (u8 i = 0; i < 4; i++) {
        if (hatState & (1 << i))
            return (i + 1);
    }
    return 0;
}

void loop() {
    u8      pin;
    u8      state;
    u8      shift;
    u8      idx;
    u8      btnNo;
    u8      pressed;
    u8      hatState;
    u8      changed;
    s16     adcHat;
    u16     LX, LY;
    u16     RX, RY;
    long    ts;

    ts = millis();

    if (ts - mLastStickTS > TIMEOUT_STICK_REPORT) {
        pressed = 0;
        for (u8 i = 0; i < sizeof(TBL_PIN_BUTTONS); i++) {
            pin   = pgm_read_byte(&TBL_PIN_BUTTONS[i]);
            state = !digitalRead(pin);

            if (i == 0) {
                shift = state;
                idx   = 0;
            } else {
                idx   = shift ? (BTN_HW_CNTS + i) : i;
            }

            // check toggle
            if (state != mLastBtnState[idx]) {
                mLastBtnState[idx] = state;
                if (i == 0) {
                    // handle asynchronous shift key press / release
                    if (shift == 1) {
                        pressed = 0x80;
                        for (u8 j = 1; j < BTN_STATE_CNTS; j++) {
                            if (mLastBtnState[j]) {
                                if (mPadMode == MODE_JOYSTICK && mJoyStick != NULL) {
                                    mJoyStick->setButton(j - 1, 0);
                                } else if (mPadMode == MODE_KEYBOARD) {
                                    Keyboard.release(pgm_read_byte(&TBL_MAP_BTN_KEY[j - 1]));
                                }
                                mLastBtnState[j] = 0;
                            }
                        }
                    } else {
                        for (u8 j = BTN_HW_CNTS + 1; j < BTN_STATE_CNTS; j++) {
                            if (mLastBtnState[j]) {
                                if (mPadMode == MODE_JOYSTICK && mJoyStick != NULL) {
                                    mJoyStick->setButton(j - 1, 0);
                                } else if (mPadMode == MODE_KEYBOARD) {
                                    Keyboard.release(pgm_read_byte(&TBL_MAP_BTN_KEY[j - 1]));
                                }
                                mLastBtnState[j] = 0;
                            }
                        }
                    }
                } else {
                    if (idx < BTN_STATE_CNTS) {
                        switch (mPadMode) {
                            case MODE_JOYSTICK:
                                if (mJoyStick != NULL) {
                                    mJoyStick->setButton(idx - 1, state);
                                }
                                break;
                                
                            case MODE_KEYBOARD:
                                if (state) {
                                    Keyboard.press(pgm_read_byte(&TBL_MAP_BTN_KEY[idx - 1]));
                                } else {
                                    Keyboard.release(pgm_read_byte(&TBL_MAP_BTN_KEY[idx - 1]));
                                }
                                break;
                                
                            case MODE_MOUSE:
                                if ((idx - 1) < sizeof(TBL_MAP_BTN_MOUSE)) {
                                    if (state) {
                                        Mouse.press(pgm_read_byte(&TBL_MAP_BTN_MOUSE[idx - 1]));
                                    } else {
                                        Mouse.release(pgm_read_byte(&TBL_MAP_BTN_MOUSE[idx - 1]));
                                    }
                                } else {
                                    if (mJoyStick != NULL) {
                                        mJoyStick->setButton(idx - 1, state);
                                    }
                                }
                                break;
                                
                            case MODE_OSD:
                                if (mJoyStick != NULL) {
                                    if (pin == PIN_BTN_START) {
                                        mJoyStick->setButton(BTN_REPORT_CNTS - 1, state);
                                    } else {
                                        if (mJoyStick != NULL) {
                                            mJoyStick->setButton(idx - 1, state);
                                        }
                                    }
                                }
                                break;
                        }
                    }
                    pressed++;
                }
            }
        }

        //
        // process hat buttons
        //
        adcHat = analogReadAvg(PIN_A_AXIS_HAT_X);
        if (adcHat > HAT_ADC_NO_KEY) {
            hatState = HAT_NONE;
        } else if (adcHat > HAT_ADC_RIGHT_UP) {
            hatState = HAT_RIGHT;
        } else {
            hatState = HAT_LEFT;
        }

        adcHat = analogReadAvg(PIN_A_AXIS_HAT_Y);
        if (adcHat > HAT_ADC_NO_KEY) {
            hatState |= HAT_NONE;
        } else if (adcHat > HAT_ADC_RIGHT_UP) {
            hatState |= HAT_UP;
        } else {
            hatState |= HAT_DOWN;
        }

        if (mLastHatState != hatState) {
            printf(F("shift:%d, hatState:%d\n"), shift, hatState);
            
            // input mode change
            if (shift == 1 && hatState > HAT_NONE) {
                switch (hatState) {
                    case HAT_LEFT:
#ifdef FEATURE_KEYBOARD
                        mPadMode = MODE_KEYBOARD;
#else
                        mPadMode = MODE_MOUSE;
#endif
                        break;
                        
                    case HAT_RIGHT:
                        mPadMode = MODE_JOYSTICK;
#ifdef FEATURE_KEYBOARD
                        // USB re-enumeration for noobs
                        if (mJoyStick == NULL) {
                            mResetFlag = MAGIC_ID;
                            wdt_enable(WDTO_15MS);
                            // reset
                        }
#endif
                        break;
                        
                    case HAT_UP:
                        mPadMode = MODE_OSD;
                        break;
                }
                printf(F("mode %d\n"), mPadMode);
            }

            // handle keys w.r.t mode
            switch (mPadMode) {
                case MODE_JOYSTICK:
                    if (mJoyStick != NULL) {
                        mJoyStick->setHatSwitch(0, pgm_read_word(&TBL_ANGLES[hatState]));
                    }
                    break;
                    
                case MODE_KEYBOARD:
                    changed = mLastHatState ^ hatState;

                    for (u8 i = 0; i < sizeof(TBL_MAP_HAT_KEY) / 2; i++) {
                        u8 hat = pgm_read_byte(&TBL_MAP_HAT_KEY[i * 2]);
                        u8 key = pgm_read_byte(&TBL_MAP_HAT_KEY[i * 2 + 1]);

                        if (changed & hat) {
                            if (hatState & hat) {
                                Keyboard.press(key);
                            } else {
                                Keyboard.release(key);
                            }
                        }
                    }
                    break;
                    
                case MODE_OSD:
                    // release previous key
                    idx = getHatIndex(mLastHatState);
                    if (idx > 0 && mJoyStick != NULL) {
                        mJoyStick->setButton(BTN_ONLY_CNTS + idx - 1, 0);
                    }
                    
                    // press current key
                    idx = getHatIndex(hatState);
                    if (idx > 0 && mJoyStick != NULL) {
                        mJoyStick->setButton(BTN_ONLY_CNTS + idx - 1, 1);
                    }
                    break;
            }
            pressed++;
            mLastHatState = hatState;
        }


        //
        // analog sticks
        //
        LX = analogReadAvg(PIN_A_AXIS_LEFT_X);
        LY = 1023 - analogReadAvg(PIN_A_AXIS_LEFT_Y);

        RX = analogReadAvg(PIN_A_AXIS_RIGHT_X);
        RY = 1023 - analogReadAvg(PIN_A_AXIS_RIGHT_Y);

        if (mIsCalMode) {
            mCalInfo.left.minX = MIN(LX, mCalInfo.left.minX);
            mCalInfo.left.maxX = MAX(LX, mCalInfo.left.maxX);
            mCalInfo.left.minY = MIN(LY, mCalInfo.left.minY);
            mCalInfo.left.maxY = MAX(LY, mCalInfo.left.maxY);

            mCalInfo.right.minX = MIN(RX, mCalInfo.right.minX);
            mCalInfo.right.maxX = MAX(RX, mCalInfo.right.maxX);
            mCalInfo.right.minY = MIN(RY, mCalInfo.right.minY);
            mCalInfo.right.maxY = MAX(RY, mCalInfo.right.maxY);
            //printf(F("LX:%4d - %4d, LY:%4d - %4d, RX:%4d - %4d, RY:%4d - %4d\n"),
            //    mCalInfo.left.minX, mCalInfo.left.maxX, mCalInfo.left.minY, mCalInfo.left.maxY,
            //    mCalInfo.right.minX, mCalInfo.right.maxX, mCalInfo.right.minY, mCalInfo.right.maxY);
        }

        if (mPadMode == MODE_MOUSE) {
            s16 mx = getMouseMove(LX, mCalInfo.left.minX, mCalInfo.left.maxX, mLastBtnState[4]);
            s16 my = getMouseMove(LY, mCalInfo.left.minY, mCalInfo.left.maxY, mLastBtnState[4]);
            Mouse.move(mx, my, 0);
        } else if (mJoyStick != NULL) {
            if (LX != mLastLX) {
                mJoyStick->setXAxis(LX);
                mLastLX = LX;
            }
            if (LY != mLastLY) {
                mJoyStick->setYAxis(LY);
                mLastLY = LY;
            }
            if (RX != mLastRX) {
                mJoyStick->setZAxis(RX);
                mLastRX = RX;
            }
            if (RY != mLastRY) {
                mJoyStick->setRzAxis(RY);
                mLastRY = RY;
            }
        }


        //
        // check if only shift key is double clicked for calibration
        //
        if (pressed == 0x80) {
            if (mShiftOnlyCtr == 0) {
                mFirstShiftOnlyTS = ts;
            }
            if ((ts - mFirstShiftOnlyTS) < TIMEOUT_SHIFT_MCLICKS) {
                mShiftOnlyCtr++;
            }
            printf(F("shift_btn %x %d %d\n"), pressed, mShiftOnlyCtr, ts);
        }

        if (mFirstShiftOnlyTS > 0 && (ts - mFirstShiftOnlyTS) > TIMEOUT_SHIFT_MCLICKS) {
            if (mShiftOnlyCtr == 2) {
                printf(F("cal change !! \n"));
                mIsCalMode = !mIsCalMode;
                if (mIsCalMode) {
                    // set invalid range for calibration
                    mCalInfo.left.minX = 8192;
                    mCalInfo.left.maxX = 0;
                    mCalInfo.left.minY = 8192;
                    mCalInfo.left.maxY = 0;
                    mCalInfo.right= mCalInfo.left;
                    printf(F("cal mode enter\n"));
                } else {
                    // save min / max range
                    printf(F("cal mode exit\n"));
                    mCalInfo.dwMagicID = MAGIC_ID;
                    EEPROM.put(0, mCalInfo);
                    setAxisRange(&mCalInfo);
                }
            }
            mShiftOnlyCtr    = 0;
            mFirstShiftOnlyTS = 0;
        }
        
        mLastStickTS = ts;
    }
    mMSP->handleRX();
}
