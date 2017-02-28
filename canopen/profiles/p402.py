# inspired by the NmtMaster code

from canopen import Node, NodeScanner

# status word 0x6041 bitmask and values in the list in the dictionary value
POWER_STATES_402 = {
    'NOT READY TO SWITCH ON': [0x4F, 0x00],
    'SWITCH ON DISABLED'    : [0x4F, 0x40],
    'READY TO SWITCH ON'    : [0x6F, 0x21],
    'SWITCHED ON'           : [0x6F, 0x23],
    'OPERATION ENABLED'     : [0x6F, 0x27],
    'FAULT'                 : [0x4F, 0x08],
    'FAULT REACTION ACTIVE' : [0x4F, 0x0F],
    'QUICK STOP ACTIVE'     : [0x6F, 0x07]
}

# control word 0x6040
POWER_STATE_COMMANDS = {
    'SWITCH ON DISABLED'    : 0x80,
    'DISABLE VOLTAGE'       : 0x04,
    'READY TO SWITCH ON'    : 0x06,
    'SWITCHED ON'           : 0x07,
    'OPERATION ENABLED'     : 0x0F,
    'QUICK STOP ACTIVE'     : 0x02
}

COMMAND_TO_POWER_STATE = {
    0x80: 'SWITCH ON DISABLED',
    0x02: 'SWITCH ON DISABLED',
    0x06: 'READY TO SWITCH ON',
    0x07: 'SWITCHED ON',
    0x0F: 'OPERATION ENABLED',
    0x02: 'QUICK STOP ACTIVE'
}

class Node402(Node):
    """A CANopen CiA 402 profile slave node.

    :param int node_id:
        Node ID (set to None or 0 if specified by object dictionary)
    :param object_dictionary:
        Object dictionary as either a path to a file, an ``ObjectDictionary``
        or a file like object.
    :type object_dictionary: :class:`str`, :class:`canopen.ObjectDictionary`
    """

    def __init__(self, node_id, object_dictionary):
        super(Node402, self).__init__(node_id, object_dictionary)
        self.powerstate_402 = PowerStateMachine(self)
        self.powerstate_402.network = self.network

    def setup_402_state_machine(self):
        # setup TPDO1 for this node
        # TPDO1 will transmit the statusword of the 402 control state machine
        # first read the current PDO setup and only change TPDO1
        print(self.nmt.state)
        self.nmt.state = 'PRE-OPERATIONAL'
        self.pdo.tx[1].read()
        self.pdo.tx[1].clear()
        # Use register as to stay manufacturer agnostic
        self.pdo.tx[1].add_variable(0x6041)
        # add callback to listen to TPDO1 and change 402 state
        self.pdo.tx[1].add_callback(self.powerstate_402.on_PDO1_callback)
        self.pdo.tx[1].trans_type = 255
        self.pdo.tx[1].enabled = True
        self.pdo.tx[1].save()
        self.nmt.state = 'OPERATIONAL'

class PowerStateMachine(object):
    """A CANopen CiA 402 Power State machine. Listens to state changes
    of the DS402 Power State machine by means of TPDO 1 Statusword.

    - Controlword 0x6040 causes transitions
    - Statusword 0x6041 gives the current state

    """

    def __init__(self, node):
        self.id = node.id
        self.node = node
        self._state = 'NOT READY TO SWITCH ON'

    @staticmethod
    def on_PDO1_callback(mapobject):
        # this function receives a map object.
        # this map object is then used for changing the
        # Node402.PowerstateMachine._state by reading the statusword
        # The TPDO1 is defined in setup_402_state_machine
        statusword = mapobject[0].raw
        for key, value in POWER_STATES_402.iteritems():
    		# check if the value after applying the bitmask (value[0])
    		# corresponds with the value[1] to determine the current status
            bitmaskvalue = statusword & value[0]
            if bitmaskvalue == value[1]:
                mapobject.pdo_node.node.powerstate_402._state = key

    @property
    def state(self):
        """Attribute to get or set node's state as a string.

        States of the node can be one of:

        - 'NOT READY TO SWITCH ON'
        - 'SWITCH ON DISABLED'
        - 'READY TO SWITCH ON'
        - 'SWITCHED ON'
        - 'OPERATION ENABLED'
        - 'FAULT'
        - 'FAULT REACTION ACTIVE'
        - 'QUICK STOP ACTIVE'

        States to switch to can be one of:

        - 'SWITCH ON DISABLED'
        - 'DISABLE VOLTAGE'
        - 'READY TO SWITCH ON'
        - 'SWITCHED ON'
        - 'OPERATION ENABLED'
        - 'QUICK STOP ACTIVE'

        """
        if self._state in POWER_STATES_402.values():
            return POWER_STATES_402[self._state]
        else:
            return self._state

    @state.setter
    def state(self, new_state):
        if new_state in POWER_STATE_COMMANDS:
            code = POWER_STATE_COMMANDS[new_state]
        else:
            raise ValueError("'%s' is an invalid state. Must be one of %s." %
                             (new_state, ", ".join(POWER_STATE_COMMANDS)))
        # send the control word in a manufacturer agnostic way
        # by not using the EDS ParameterName but the register number
        self.node.sdo[0x6040].raw = code
