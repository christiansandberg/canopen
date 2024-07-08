import unittest

import canopen
import can
from .util import SAMPLE_EDS


class TestNetwork(unittest.TestCase):

    def setUp(self):
        network = canopen.Network()
        with self.assertLogs():
            network.add_node(2, SAMPLE_EDS)
        network.add_node(3, network[2].object_dictionary)
        self.network = network

    def test_add_node(self):
        node = self.network[2]
        self.assertIsInstance(node, canopen.Node)
        self.assertEqual(node.id, 2)
        self.assertEqual(self.network[2], node)
        self.assertEqual(len(self.network), 2)

    def test_notify(self):
        node = self.network[2]
        self.network.notify(0x82, b'\x01\x20\x02\x00\x01\x02\x03\x04', 1473418396.0)
        self.assertEqual(len(node.emcy.active), 1)
        self.network.notify(0x702, b'\x05', 1473418396.0)
        self.assertEqual(node.nmt.state, 'OPERATIONAL')
        self.assertListEqual(self.network.scanner.nodes, [2])

    def test_send(self):
        bus = can.interface.Bus(interface="virtual", channel=1)
        self.addCleanup(bus.shutdown)

        self.network.connect(interface="virtual", channel=1)
        self.addCleanup(self.network.disconnect)

        # Send standard ID
        self.network.send_message(0x123, [1, 2, 3, 4, 5, 6, 7, 8])
        msg = bus.recv(1)
        self.assertIsNotNone(msg)
        self.assertEqual(msg.arbitration_id, 0x123)
        self.assertFalse(msg.is_extended_id)
        self.assertSequenceEqual(msg.data, [1, 2, 3, 4, 5, 6, 7, 8])

        # Send extended ID
        self.network.send_message(0x12345, [])
        msg = bus.recv(1)
        self.assertIsNotNone(msg)
        self.assertEqual(msg.arbitration_id, 0x12345)
        self.assertTrue(msg.is_extended_id)

    def test_send_periodic(self):
        from threading import Event

        DATA1 = bytes([1, 2, 3])
        DATA2 = bytes([4, 5, 6])
        COB_ID = 0x123
        TIMEOUT = 0.1
        self.network.connect(
            interface="virtual",
            channel=1,
            receive_own_messages=True
        )
        self.addCleanup(self.network.disconnect)

        acc = []
        event = Event()

        def hook(id_, data, ts):
            acc.append(data)
            event.set()

        self.network.subscribe(COB_ID, hook)
        self.addCleanup(self.network.unsubscribe, COB_ID)

        task = self.network.send_periodic(COB_ID, DATA1, TIMEOUT/10)
        self.addCleanup(task.stop)

        event.wait(TIMEOUT)
        self.assertEqual(acc[0], DATA1)

        # Update task data.
        task.update(DATA2)
        event.clear()
        event.wait(TIMEOUT)

        self.assertEqual(acc[-1], DATA2)


class TestScanner(unittest.TestCase):

    def test_passive_scanning(self):
        scanner = canopen.network.NodeScanner()
        scanner.on_message_received(0x586)
        scanner.on_message_received(0x587)
        scanner.on_message_received(0x586)
        self.assertListEqual(scanner.nodes, [6, 7])


if __name__ == "__main__":
    unittest.main()
