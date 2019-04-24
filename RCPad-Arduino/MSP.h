/*
 This project is free software: you can redistribute it and/or modify
 it under the terms of the GNU General Public License as published by
 the Free Software Foundation, either version 3 of the License, or
 (at your option) any later version.

 This program is distributed in the hope that it will be useful,
 but WITHOUT ANY WARRANTY; without even the implied warranty of
 MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
 GNU General Public License for more details.
 see <http://www.gnu.org/licenses/>
*/

#ifndef _MSP_H_
#define _MSP_H_

#include "common.h"

#define MAX_PACKET_SIZE 32

class MSP
{
private:
    Serial_  *mSerial;

    typedef enum
    {
        STATE_IDLE,
        STATE_HEADER_START,
        STATE_HEADER_M,
        STATE_HEADER_ARROW,
        STATE_HEADER_SIZE,
        STATE_HEADER_CMD
    } STATE_T;
    //

    // variables
    u8   mRxPacket[MAX_PACKET_SIZE];

    u8   mState;
    u8   mOffset;
    u8   mDataSize;
    u8   mCheckSum;
    u8   mCmd;

    void sendResponse(bool ok, u8 cmd, u8 *data, u8 size);
    void evalCommand(u8 cmd, u8 *data, u8 size);
public:
    MSP(Serial_ *serial);
    u8   handleRX(void);
    
    virtual s8 onReceived(u8 cmd, u8 *data, u8 size, u8 *res) = 0;
};

#endif
