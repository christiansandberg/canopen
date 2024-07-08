import time
import unittest

import canopen
from .util import SAMPLE_EDS


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
