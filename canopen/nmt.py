import threading
import logging
import struct
import time

from .network import CanError

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
            logger.info("Received heartbeat can-id %d, state is %d", can_id, new_state)
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

class NmtSlave(object):
    """
    Handles the NMT state and handles heartbeat NMT service.
    """
    def __init__(self, node_id, local_node):
        self._id = node_id
        self.network = None
        self._state = 0
        self._timer_thread = None
        self._thread_stop = None
        self._heartbeat_time_ms = 0
        self._local_node = local_node

    def on_command(self, can_id, data, timestamp):
        (cmd, node_id) = struct.unpack_from("<BB", data)

        if node_id == self._id:
            logger.info("Received command %d", cmd)
            self.state = NMT_STATES[COMMAND_TO_STATE[cmd]]

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
            new_nmt_state = COMMAND_TO_STATE[NMT_COMMANDS[new_state]]

            logger.info("New NMT state %s, old state %s",
                        NMT_STATES[new_nmt_state], NMT_STATES[self._state])

            # The heartbeat service should start on the transition
            # between INITIALIZING and PRE-OPERATIONAL state
            if self._state is 0 and new_nmt_state is 127:
                self.stop_heartbeat()
                heartbeat_time_ms = self._local_node.sdo[0x1017].raw
                self.start_heartbeat(heartbeat_time_ms)

            self._state = new_nmt_state
        else:
            raise ValueError("'%s' is an invalid state. Must be one of %s." %
                             (new_state, ", ".join(NMT_COMMANDS)))

    def start_heartbeat(self, heartbeat_time_ms):
        """Start the hearbeat service.

        :param int hearbeat_time
            The heartbeat time in ms. If the heartbeat time is 0
            the heartbeating will not start.
        """
        self._heartbeat_time_ms = heartbeat_time_ms

        if heartbeat_time_ms > 0:
            logger.info("Start the hearbeat timer, interval is %d ms", self._heartbeat_time_ms)
            self._thread_stop = threading.Event()
            self._timer_thread = threading.Thread(target=self.send_heartbeat,
                                                  args=(self._thread_stop,))
            self._timer_thread.daemon = True
            self._timer_thread.start()

    def stop_heartbeat(self):
        """Stop the hearbeat service."""
        if self._timer_thread:
            logger.info("Stop the heartbeat timer")
            self._thread_stop.set()
            self._timer_thread = None

    def send_heartbeat(self, stop_event):
        """Send heartbeat on a regular interval"""
        while not stop_event.is_set():
            stop_event.wait(self._heartbeat_time_ms/1000)
            logger.debug("Sending heartbeat, NMT state is  %s", NMT_STATES[self._state])

            try:
                self.network.send_message(1792 + self._id, [self._state])
            except CanError as e:
                # We will just try again
                logger.info("Failed to send heartbeat due to: %s", str(e))
