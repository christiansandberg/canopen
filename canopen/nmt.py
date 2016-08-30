import threading


NMT_STATES = {
    0: 'INIT',
    4: 'STOPPED',
    5: 'OPERATIONAL',
    80: 'SLEEP',
    96: 'STANDBY',
    127: 'PRE OPERATIONAL'
}


NMT_TRANSITIONS = {
    'OPERATIONAL': 1,
    'STOPPED': 2,
    'SLEEP': 80,
    'STANDBY': 96,
    'PRE OPERATIONAL': 128,
    'INIT': 129,
    'RESET COMMUNICATION': 130
}


class NmtNode(object):

    def __init__(self):
        self._state = 0
        self.state_change = threading.Condition()
        self.parent = None

    def on_heartbeat(self, can_id, data):
        new_state = data[0]
        with self.state_change:
            if new_state != self._state:
                self._state = new_state
                self.state_change.notify_all()

    def send_command(self, code):
        self.parent.network.send_message(0, [code, self.parent.id])

    @property
    def state(self):
        return NMT_STATES[self._state]

    @state.setter
    def state(self, transition):
        if isinstance(transition, int):
            code = transition
        elif transition in NMT_TRANSITIONS:
            code = NMT_TRANSITIONS[transition]
        else:
            raise KeyError("'%s' is an invalid state. Must be one of %s." %
                           (transition, ", ".join(NMT_TRANSITIONS)))

        self.send_command(code)

    def wait_for_state_change(self, timeout=10):
        with self.state_change:
            self.state_change.wait(timeout)
