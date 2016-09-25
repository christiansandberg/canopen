Network management (NMT)
========================

The NMT protocols are used to issue state machine change commands
(e.g. to start and stop the devices), detect remote device bootups and
error conditions.

The Module control protocol is used by the NMT master to change the state of
the devices. The CAN-frame COB-ID of this protocol is always 0, meaning that it
has a function code 0 and node ID 0, which means that every node in the network
will process this message. The actual node ID, to which the command is meant to,
is given in the data part of the message (at the second byte). This can also be
0, meaning that all the devices on the bus should go to the indicated state.

The Heartbeat protocol is used to monitor the nodes in the network and verify
that they are alive. A heartbeat producer (usually a slave device) periodically
sends a message with the binary function code of 1110 and its node ID
(COB-ID = 0x700 + node ID). The data part of the frame contains a byte
indicating the node status. The heartbeat consumer reads these messages.

CANopen devices are required to make the transition from the state Initializing
to Pre-operational automatically during bootup. When this transition is made,
a single heartbeat message is sent to the bus. This is the bootup protocol.
