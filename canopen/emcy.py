import struct
import logging


logger = logging.getLogger(__name__)


# Error code, error register, vendor specific data
EMCY_STRUCT = struct.Struct("<HB5s")


DESCRIPTIONS = [
    # Code   Mask    Description
    (0x0000, 0xFF00, "Error Reset / No Error"),
    (0x1000, 0xFF00, "Generic Error"),
    (0x2000, 0xF000, "Current"),
    (0x3000, 0xF000, "Voltage"),
    (0x4000, 0xF000, "Temperature"),
    (0x5000, 0xFF00, "Device Hardware"),
    (0x6000, 0xF000, "Device Software"),
    (0x7000, 0xFF00, "Additional Modules"),
    (0x8000, 0xF000, "Monitoring"),
    (0x9000, 0xFF00, "External Error"),
    (0xF000, 0xFF00, "Additional Functions"),
    (0xFF00, 0xFF00, "Device Specific")
]


class EmcyConsumer(object):

    def __init__(self):
        #: Log of all received EMCYs for this node
        self.log = []
        #: Only active EMCYs. Will be cleared on Error Reset
        self.active = []

    def on_emcy(self, can_id, data, timestamp):
        if can_id == 0x80:
            # This is a SYNC message
            return
        code, register, data = EMCY_STRUCT.unpack(data)
        if code & 0xFF == 0:
            # Error reset
            self.active = []
        else:
            entry = EmcyError(code, register, data, timestamp)
            self.log.append(entry)
            self.active.append(entry)


class EmcyError(Exception):
    """EMCY exception."""

    def __init__(self, code, register, data, timestamp):
        #: EMCY code
        self.code = code
        #: Error register
        self.register = register
        #: Vendor specific data
        self.data = data
        #: Timestamp of message
        self.timestamp = timestamp

    def get_desc(self):
        for code, mask, description in DESCRIPTIONS:
            if self.code & mask == code:
                return description
        return ""

    def __str__(self):
        text = "Code 0x{:04X}".format(self.code)
        description = self.get_desc()
        if description:
            text = text + ", " + description
        return text
