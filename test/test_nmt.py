import time
import unittest

import canopen
from canopen.nmt import NMT_STATES, NMT_COMMANDS
from .util import SAMPLE_EDS


class TestNmtBase(unittest.TestCase):
    def setUp(self):
        node_id = 2
        self.node_id = node_id
        self.nmt = canopen.nmt.NmtBase(node_id)

    def test_send_command(self):
        dataset = (
            "OPERATIONAL",
            "PRE-OPERATIONAL",
            "SLEEP",
            "STANDBY",
            "STOPPED",
        )
        for cmd in dataset:
            with self.subTest(cmd=cmd):
                code = NMT_COMMANDS[cmd]
                self.nmt.send_command(code)
                self.assertNotEqual(self.nmt.state, "INITIALISING")

    def test_state_getset(self):
        for state in NMT_STATES.values():
            with self.subTest(state=state):
                self.nmt.state = state
                self.assertEqual(self.nmt.state, state)

    def test_state_set_invalid(self):
        with self.assertRaisesRegex(ValueError, "INVALID"):
            self.nmt.state = "INVALID"

    def test_state_get_invalid(self):
        # This is a known bug; it will be changed in gh-500.
        self.nmt._state = 255
        self.assertEqual(self.nmt.state, 255)


class TestNmtSlave(unittest.TestCase):
    def setUp(self):
        self.network1 = canopen.Network()
        self.network1.connect("test", interface="virtual")
        self.remote_node = self.network1.add_node(2, SAMPLE_EDS)

        self.network2 = canopen.Network()
        self.network2.connect("test", interface="virtual")
        self.local_node = self.network2.create_node(2, SAMPLE_EDS)
        self.remote_node2 = self.network1.add_node(3, SAMPLE_EDS)
        self.local_node2 = self.network2.create_node(3, SAMPLE_EDS)

    def tearDown(self):
        self.network1.disconnect()
        self.network2.disconnect()

    def test_start_two_remote_nodes(self):
        self.remote_node.nmt.state = "OPERATIONAL"
        # Line below is just so that we are sure the client have received the command
        # before we do the check
        time.sleep(0.1)
        slave_state = self.local_node.nmt.state
        self.assertEqual(slave_state, "OPERATIONAL")

        self.remote_node2.nmt.state = "OPERATIONAL"
        # Line below is just so that we are sure the client have received the command
        # before we do the check
        time.sleep(0.1)
        slave_state = self.local_node2.nmt.state
        self.assertEqual(slave_state, "OPERATIONAL")

    def test_stop_two_remote_nodes_using_broadcast(self):
        # This is a NMT broadcast "Stop remote node"
        # ie. set the node in STOPPED state
        self.network1.send_message(0, [2, 0])

        # Line below is just so that we are sure the slaves have received the command
        # before we do the check
        time.sleep(0.1)
        slave_state = self.local_node.nmt.state
        self.assertEqual(slave_state, "STOPPED")
        slave_state = self.local_node2.nmt.state
        self.assertEqual(slave_state, "STOPPED")

    def test_heartbeat(self):
        self.assertEqual(self.remote_node.nmt.state, "INITIALISING")
        self.assertEqual(self.local_node.nmt.state, "INITIALISING")
        self.local_node.nmt.state = "OPERATIONAL"
        self.local_node.sdo[0x1017].raw = 100
        time.sleep(0.2)
        self.assertEqual(self.remote_node.nmt.state, "OPERATIONAL")

        self.local_node.nmt.stop_heartbeat()


if __name__ == "__main__":
    unittest.main()
