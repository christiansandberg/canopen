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


class EmcyNode(object):

    def __init__(self):
        self.log = []

    def on_emcy(self, can_id, data, timestamp):
        code, register, data = EMCY_STRUCT.unpack(data)
        if code & 0xFF == 0:
            entry = ErrorReset(code, register, data, timestamp)
        else:
            entry = EmcyError(code, register, data, timestamp)
        self.log.append(entry)


class ErrorReset(object):

    def __init__(self, code, register, data, timestamp):
        self.code = code
        self.register = register
        self.data = data
        self.timestamp = timestamp


class EmcyError(Exception):

    def __init__(self, code, register, data, timestamp):
        self.code = code
        self.register = register
        self.data = data
        self.timestamp = timestamp

    @property
    def desc(self):
        for code, mask, description in DESCRIPTIONS:
            if self.code & mask == code:
                return description
        return None

    def __str__(self):
        text = "Code 0x{:04X}".format(self.code)
        description = self.desc
        if description:
            text = text + ", " + description
        return text
