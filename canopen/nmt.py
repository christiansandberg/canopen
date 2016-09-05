import threading


NMT_STATES = {
    0: 'INIT',
    4: 'STOPPED',
    5: 'OPERATIONAL',
    80: 'SLEEP',
    96: 'STANDBY',
    127: 'PRE OPERATIONAL'
}


NMT_COMMANDS = {
    'OPERATIONAL': 1,
    'STOPPED': 2,
    'SLEEP': 80,
    'STANDBY': 96,
    'PRE OPERATIONAL': 128,
    'INIT': 129,
    'RESET': 129,
    'RESET COMMUNICATION': 130
}


class NmtNode(object):

    def __init__(self):
        self._state = 0
        self.state_change = threading.Condition()
        self.parent = None

    def on_heartbeat(self, can_id, data):
        new_state = data[0]
        if new_state != self._state:
            with self.state_change:
                self._state = new_state
                self.state_change.notify_all()

    def send_command(self, code):
        self.parent.network.send_message(0, [code, self.parent.id])

    @property
    def state(self):
        return NMT_STATES[self._state]

    @state.setter
    def state(self, new_state):
        if new_state in NMT_COMMANDS:
            code = NMT_COMMANDS[new_state]
        else:
            raise KeyError("'%s' is an invalid state. Must be one of %s." %
                           (new_state, ", ".join(NMT_COMMANDS)))

        self.send_command(code)

    def wait_for_state_change(self, timeout=10):
        with self.state_change:
            self.state_change.wait(timeout)
