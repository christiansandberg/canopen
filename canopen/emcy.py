import struct
import logging
import threading
import time


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
        self.emcy_received = threading.Condition()

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
            #print("EMCY received for node %d: %s" % (can_id & 0x7F, entry))
            with self.emcy_received:
                self.log.append(entry)
                self.active.append(entry)
                self.emcy_received.notify_all()

    def reset(self):
        """Reset log and active lists."""
        self.log = []
        self.active = []

    def wait(self, emcy_code=None, timeout=10):
        """Wait for a new EMCY to arrive.

        :param int emcy_code: EMCY code to wait for
        :param float timeout: Max time in seconds to wait

        :return: The EMCY exception object or None if timeout
        :rtype: canopen.emcy.EmcyError
        """
        end_time = time.time() + timeout
        while True:
            with self.emcy_received:
                prev_log_size = len(self.log)
                self.emcy_received.wait(timeout)
                if len(self.log) == prev_log_size:
                    # Resumed due to timeout
                    return None
                # Get last logged EMCY
                emcy = self.log[-1]
                logger.info("Got %s", emcy)
                if time.time() > end_time:
                    # No valid EMCY received on time
                    return None
                if emcy_code is None or emcy.code == emcy_code:
                    # This is the one we're interested in
                    return emcy


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
