import logging
import struct
try:
    import queue
except ImportError:
    import Queue as queue


logger = logging.getLogger(__name__)

SWITCH_MODE_GLOBAL = 0x04
CONFIGURE_NODE_ID = 0x11
CONFIGURE_BIT_TIMING = 0x13
STORE_CONFIGURATION = 0x17
INQUIRE_NODE_ID = 0x5E

ERROR_NONE = 0
ERROR_INADMISSIBLE = 1

ERROR_STORE_NONE = 0
ERROR_STORE_NOT_SUPPORTED = 1
ERROR_STORE_ACCESS_PROBLEM = 2

ERROR_VENDOR_SPECIFIC = 0xff


class LssMaster(object):
    """The Master of Layer Setting Services"""

    LSS_TX_COBID = 0x7E5
    LSS_RX_COBID = 0x7E4

    NORMAL_MODE = 0x00
    CONFIGURATION_MODE = 0x01

    #: Max retries for any LSS request
    MAX_RETRIES = 3

    #: Max time in seconds to wait for response from server
    RESPONSE_TIMEOUT = 0.5

    def __init__(self):
        self.network = None
        self._node_id = 0
        self._data = None
        self._mode_state = self.NORMAL_MODE
        self.responses = queue.Queue()

    def send_switch_mode_global(self, mode):
        """switch mode to CONFIGURATION_MODE or NORMAL_MODE.
        There is no reply for this request

        :param int mode:
            CONFIGURATION_MODE or NORMAL_MODE
        """
        # LSS messages are always a full 8 bytes long.
        # Unused bytes are reserved and should be initialized with 0.
        message = bytearray(8)

        if self._mode_state != mode:
            message[0] = SWITCH_MODE_GLOBAL
            message[1] = mode
            self._mode_state = mode
            self.__send_command(message)

    def __send_inquire_node_id(self):
        """
        :return: Current node id
        :rtype: int
        """
        message = bytearray(8)
        message[0] = INQUIRE_NODE_ID
        current_node_id, nothing = self.__send_command(message)

        return current_node_id

    def __send_configure(self, key, value1=0, value2=0):
        """Send a message to set a key with values"""
        message = bytearray(8)
        message[0] = key
        message[1] = value1
        message[2] = value2
        error_code, error_extension = self.__send_command(message)
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
        """Set the node id

        :param int new_node_id:
            new node id to set
        """
        self.send_switch_mode_global(self.CONFIGURATION_MODE)
        self.__send_configure(CONFIGURE_NODE_ID, new_node_id)

    def configure_bit_timing(self, new_bit_timing):
        """Set the bit timing.

        :param int new_bit_timing:
            bit timing index.
            0: 1 MBit/sec, 1: 800 kBit/sec,
            2: 500 kBit/sec, 3: 250 kBit/sec,
            4: 125 kBit/sec  5: 100 kBit/sec,
            6: 50 kBit/sec, 7: 20 kBit/sec,
            8: 10 kBit/sec
        """
        self.send_switch_mode_global(self.CONFIGURATION_MODE)
        self.__send_configure(CONFIGURE_BIT_TIMING, 0, new_bit_timing)

    def store_configuration(self):
        """Store node id and baud rate.
        """
        self.__send_configure(STORE_CONFIGURATION)

    def __send_command(self, message):
        """Send a LSS operation code to the network

        :param bytearray message:
            LSS request message.
        """

        retries_left = self.MAX_RETRIES

        message_str = " ".join(["{:02x}".format(x) for x in message])
        logger.info(
            "Sending LSS message %s", message_str)

        response = None
        if not self.responses.empty():
            # logger.warning("There were unexpected messages in the queue")
            self.responses = queue.Queue()

        while retries_left:
            # Wait for node to respond
            self.network.send_message(self.LSS_TX_COBID, message)

            # There is no response for SWITCH_MODE_GLOBAL message
            if message[0] == SWITCH_MODE_GLOBAL:
                return

            try:
                response = self.responses.get(
                    block=True, timeout=self.RESPONSE_TIMEOUT)
            except queue.Empty:
                retries_left -= 1
            else:
                break

        if not response:
            raise LssError("No LSS response received")
        if retries_left < self.MAX_RETRIES:
            logger.warning("There were some issues while communicating with the node")
        res_command, message1, message2 = struct.unpack_from("BBB", response)
        if res_command != message[0]:
            raise LssError("Unexpected response (%d)" % res_command)
        self._mode_state = self.CONFIGURATION_MODE
        return message1, message2

    def on_message_received(self, can_id, data, timestamp):
        self.responses.put(bytes(data))


class LssError(Exception):
    """Some LSS operation failed."""
