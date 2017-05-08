import threading
import logging
import struct
import time

try:
    import can
    from can import Listener
    from can import CanError
except ImportError:
    # Do not fail if python-can is not installed
    can = None
    Listener = object

logger = logging.getLogger(__name__)

SWITCH_MODE_GLOBAL =    0x04
CONFIGURE_NODE_ID =     0x11
CONFIGURE_BIT_TIMING =  0x13
STORE_CONFIGURATION =   0x17
INQUIRE_NODE_ID =       0x5E

ERROR_NONE =            0
ERROR_INADMISSIBLE =    1

ERROR_STORE_NONE =              0
ERROR_STORE_NOT_SUPPORTED =     1
ERROR_STORE_ACCESS_PROBLEM =    2

ERROR_VENDOR_SPECIFIC =         0xff

LSS_TX_COBID = 0x7E5
LSS_RX_COBID = 0x7E4

class LssMaster(Listener):
    """The Master of Layer Setting Services"""

    NORMAL_MODE =           0x00
    CONFIGURATION_MODE =    0x01


    def __init__(self):
        self.network = None
        self._node_id = 0
        self._data = None
        self._mode_state = self.NORMAL_MODE
        self._is_timeout = True
        self._reply_received = threading.Condition()

    def send_switch_mode_global(self, mode):
        """There is no reply for this request
        """
        # LSS messages are always a full 8 bytes long. 
        # Unused bytes are reserved and should be initialized with 0.
        
        message = [0]*8

        if len(message) != 8:
            raise ValueError('message should be a list with 8 items')
        if self._mode_state != mode:
            message[0] = SWITCH_MODE_GLOBAL
            message[1] = mode
            self._mode_state = mode
            self.__send_command(message)

    def __send_inquire_node_id(self):
        """
        :return: int current node id
        """
        message = [0]*8
        message[0] = INQUIRE_NODE_ID
        self.__send_command(message)
        current_node_id = self.__wait_for_reply(INQUIRE_NODE_ID)[0]
        return current_node_id

    def __send_configure(self, key, value1=0, value2=0):
        """Send a message to set a key with values
        :return: int error_code, int error_extension 
        """
        message = [0]*8
        message[0] = key
        message[1] = value1
        message[2] = value2
        self.__send_command(message)
        error_code, error_extension = self.__wait_for_reply(key)
        if error_code != ERROR_NONE:
            error_msg = "LSS Error: %d" %error_code
            raise LssError(error_msg)

    def inquire_node_id(self):
        """Read the node id.
        CANopen node id must be within the range from 1 to 127.

        :return: int node id
            0 means it is not read by LSS protocol
        """
        self.send_switch_mode_global(self.CONFIGURATION_MODE)
        return self.__send_inquire_node_id()

    def configure_node_id(self, new_node_id):
        self.send_switch_mode_global(self.CONFIGURATION_MODE)
        self.__send_configure(CONFIGURE_NODE_ID, new_node_id)

    def configure_bit_timing(self, new_bit_timing):
        """Set the bit timing.

        0: 1 MBit/sec, 1: 800 kBit/sec, 
        2: 500 kBit/sec, 3: 250 kBit/sec, 
        4: 125 kBit/sec  5: 100 kBit/sec, 
        6: 50 kBit/sec, 7: 20 kBit/sec, 
        8: 10 kBit/sec
        """
        self.send_switch_mode_global(self.CONFIGURATION_MODE)
        self.__send_configure(CONFIGURE_BIT_TIMING, 0, new_bit_timing)

    def store_configuration(self):
        self.__send_configure(STORE_CONFIGURATION)

    def __send_command(self, message):
        """Send a LSS operation code to the network

        :param byte list message:
            LSS request message.
        """

        message_str = "".join(["{:02x} ".format(x) for x in message])
        logger.info(
            "Sending LSS message %s", message_str)

        self._is_timeout = True
        self.network.send_message(LSS_TX_COBID, message)
        
    def on_message_received(self, msg):
        if (msg.is_error_frame or msg.is_remote_frame or
                msg.is_extended_id or msg.arbitration_id != LSS_RX_COBID):
            return

        self._is_timeout = False
        self._data = msg.data
        with self._reply_received:
            self._reply_received.notify_all()

    def __wait_for_reply(self, opcode, timeout=1):
        """Wait until a reply message is received."""
        with self._reply_received:
            self.reply_state = None
            self._reply_received.wait(timeout)

        if self._is_timeout:
            raise LssError("LSS response is timed out")

        if self._data[0] != opcode:
            raise LssError("LSS response has a different opcode")

        self._mode_state = self.CONFIGURATION_MODE

        return self._data[1], self._data[2]

class LssError(Exception):
    """Some LSS operation failed."""
