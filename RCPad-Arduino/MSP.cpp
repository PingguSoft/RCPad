#include <Arduino.h>
#include <avr/pgmspace.h>
#include "MSP.h"

MSP::MSP(Serial_ *serial)
{
    mSerial = serial;
    mState = STATE_IDLE;
}

void MSP::sendResponse(bool ok, u8 cmd, u8 *data, u8 size)
{
    mSerial->write('$');
    mSerial->write('M');
    mSerial->write((ok ? '>' : '!'));
    
    u8 chkSumTX = 0;
    mSerial->write(size);
    chkSumTX ^= size;
    mSerial->write(cmd);
    chkSumTX ^= cmd;
    for (u8 i = 0; i < size; i++) {
        mSerial->write(*data);
        chkSumTX ^= *data;
        data++;
    }
    mSerial->write(chkSumTX);
}

void MSP::evalCommand(u8 cmd, u8 *data, u8 size)
{
    u8  buf[22];
        
    s8 ret = onReceived(cmd, data, size, (u8*)buf);
    if (ret >= 0)
        sendResponse(TRUE, cmd, buf, ret);
}

u8 MSP::handleRX(void)
{
    u8 ret = 0;
    u8 rxSize = mSerial->available();

    if (rxSize == 0)
        return ret;

    while (rxSize--) {
        u8 ch = mSerial->read();

        switch (mState) {
            case STATE_IDLE:
                if (ch == '$')
                    mState = STATE_HEADER_START;
                break;

            case STATE_HEADER_START:
                mState = (ch == 'M') ? STATE_HEADER_M : STATE_IDLE;
                break;

            case STATE_HEADER_M:
                mState = (ch == '<') ? STATE_HEADER_ARROW : STATE_IDLE;
                break;

            case STATE_HEADER_ARROW:
                if (ch > MAX_PACKET_SIZE) { // now we are expecting the payload size
                    mState = STATE_IDLE;
                    continue;
                }
                mDataSize = ch;
                mCheckSum = ch;
                mOffset   = 0;
                mState    = STATE_HEADER_SIZE;
                break;

            case STATE_HEADER_SIZE:
                mCmd       = ch;
                mCheckSum ^= ch;
                mState     = STATE_HEADER_CMD;
                break;

            case STATE_HEADER_CMD:
                if (mOffset < mDataSize) {
                    mCheckSum           ^= ch;
                    mRxPacket[mOffset++] = ch;
                } else {
                    if (mCheckSum == ch) {
                        ret = mCmd;
                        evalCommand(ret, mRxPacket, mDataSize);
                    }
                    mState = STATE_IDLE;
                    //rxSize = 0;             // no more than one command per cycle
                }
                break;
        }
    }
    return ret;
}
