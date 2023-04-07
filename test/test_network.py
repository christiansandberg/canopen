import time
import os
import unittest
import canopen

import can

EDS_PATH = os.path.join(os.path.dirname(__file__), 'sample.eds')


class TestNetwork(unittest.TestCase):

    def setUp(self):
        network = canopen.Network()
        network.add_node(2, EDS_PATH)
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
        bus = can.interface.Bus(bustype="virtual", channel=1)
        self.network.connect(bustype="virtual", channel=1)

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

        bus.shutdown()
        self.network.disconnect()

    def test_send_perodic(self):
        bus = can.interface.Bus(bustype="virtual", channel=1)
        self.network.connect(bustype="virtual", channel=1)

        task = self.network.send_periodic(0x123, [1, 2, 3], 0.01)
        time.sleep(0.1)
        # FIXME: This test is a little fragile, as the number of elements
        #        depends on the timing of the machine.
        print("Queue size: %s" % (bus.queue.qsize(),))
        self.assertTrue(9 <= bus.queue.qsize() <= 13)
        msg = bus.recv(0)
        self.assertIsNotNone(msg)
        self.assertSequenceEqual(msg.data, [1, 2, 3])
        # Update data
        task.update([4, 5, 6])
        time.sleep(0.02)
        while msg is not None and msg.data == b'\x01\x02\x03':
            msg = bus.recv(0)
        self.assertIsNotNone(msg)
        self.assertSequenceEqual(msg.data, [4, 5, 6])
        task.stop()

        bus.shutdown()
        self.network.disconnect()


class TestScanner(unittest.TestCase):

    def test_passive_scanning(self):
        scanner = canopen.network.NodeScanner()
        scanner.on_message_received(0x586)
        scanner.on_message_received(0x587)
        scanner.on_message_received(0x586)
        self.assertListEqual(scanner.nodes, [6, 7])


if __name__ == "__main__":
    unittest.main()
