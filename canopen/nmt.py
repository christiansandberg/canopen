import threading
import logging
import struct
import time


logger = logging.getLogger(__name__)


NMT_STATES = {
    0: 'INITIALISING',
    4: 'STOPPED',
    5: 'OPERATIONAL',
    80: 'SLEEP',
    96: 'STANDBY',
    127: 'PRE-OPERATIONAL'
}


NMT_COMMANDS = {
    'OPERATIONAL': 1,
    'STOPPED': 2,
    'SLEEP': 80,
    'STANDBY': 96,
    'PRE-OPERATIONAL': 128,
    'INITIALISING': 129,
    'RESET': 129,
    'RESET COMMUNICATION': 130
}


COMMAND_TO_STATE = {
    1: 5,
    2: 4,
    80: 80,
    96: 96,
    128: 127,
    129: 0,
    130: 0
}


class NmtMaster(object):
    """
    Can set the state of the node it controls using NMT commands and monitor
    the current state using the heartbeat protocol.
    """

    def __init__(self, node_id):
        self.id = node_id
        self.network = None
        self._state = 0
        self._state_received = None
        #: Timestamp of last heartbeat message
        self.timestamp = None
        self.state_update = threading.Condition()

    def on_heartbeat(self, can_id, data, timestamp):
        with self.state_update:
            self.timestamp = timestamp
            new_state, = struct.unpack("B", data)
            if new_state == 0:
                # Boot-up, will go to PRE-OPERATIONAL automatically
                self._state = 127
            else:
                self._state = new_state
            self._state_received = new_state
            self.state_update.notify_all()

    def send_command(self, code):
        """Send an NMT command code to the node.

        :param int code:
            NMT command code.
        """
        logger.info(
            "Sending NMT command 0x%X to node %d", code, self.id)
        self.network.send_message(0, [code, self.id])
        if code in COMMAND_TO_STATE:
            self._state = COMMAND_TO_STATE[code]
            logger.info("Changing NMT state to %s", self.state)

    @property
    def state(self):
        """Attribute to get or set node's state as a string.

        Can be one of:

        - 'INITIALISING'
        - 'PRE-OPERATIONAL'
        - 'STOPPED'
        - 'OPERATIONAL'
        - 'SLEEP'
        - 'STANDBY'
        - 'RESET'
        - 'RESET COMMUNICATION'
        """
        if self._state in NMT_STATES:
            return NMT_STATES[self._state]
        else:
            return self._state

    @state.setter
    def state(self, new_state):
        if new_state in NMT_COMMANDS:
            code = NMT_COMMANDS[new_state]
        else:
            raise ValueError("'%s' is an invalid state. Must be one of %s." %
                             (new_state, ", ".join(NMT_COMMANDS)))

        self.send_command(code)

    def wait_for_heartbeat(self, timeout=10):
        """Wait until a heartbeat message is received."""
        with self.state_update:
            self._state_received = None
            self.state_update.wait(timeout)
        if self._state_received is None:
            raise NmtError("No boot-up or heartbeat received")
        return self.state

    def wait_for_bootup(self, timeout=10):
        """Wait until a boot-up message is received."""
        end_time = time.time() + timeout
        while True:
            now = time.time()
            with self.state_update:
                self._state_received = None
                self.state_update.wait(end_time - now + 0.1)
            if now > end_time:
                raise NmtError("Timeout waiting for boot-up message")
            if self._state_received == 0:
                break


class NmtError(Exception):
    """Some NMT operation failed."""
