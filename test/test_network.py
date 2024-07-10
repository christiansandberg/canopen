import unittest
import threading

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
        DATA1 = bytes([1, 2, 3])
        DATA2 = bytes([4, 5, 6])
        COB_ID = 0x123
        PERIOD = 0.1
        TIMEOUT = PERIOD * 10
        self.network.connect(
            interface="virtual",
            channel=1,
            receive_own_messages=True
        )
        self.addCleanup(self.network.disconnect)

        acc = []
        condition = threading.Condition()

        def hook(_, data, ts):
            item = data, ts
            acc.append(item)
            condition.notify()

        self.network.subscribe(COB_ID, hook)
        self.addCleanup(self.network.unsubscribe, COB_ID)

        task = self.network.send_periodic(COB_ID, DATA1, PERIOD)
        self.addCleanup(task.stop)

        def periodicity():
            # Check if periodicity is established; flakiness has been observed
            # on macOS.
            if len(acc) >= 2:
                delta = acc[-1][1] - acc[-2][1]
                return round(delta, ndigits=1) == PERIOD
            return False

        # Wait for frames to arrive; then check the result.
        with condition:
            condition.wait_for(periodicity, TIMEOUT)
        self.assertTrue(all(v[0] == DATA1 for v in acc))

        # Update task data, which implicitly restarts the timer.
        # Wait for frames to arrive; then check the result.
        task.update(DATA2)
        with condition:
            acc.clear()
            condition.wait_for(periodicity, TIMEOUT)
        # Find the first message with new data, and verify that all subsequent
        # messages also carry the new payload.
        data = [v[0] for v in acc]
        idx = data.index(DATA2)
        self.assertTrue(all(v[0] == DATA2 for v in acc[idx:]))

        # Stop the task.
        task.stop()
        # A message may have been in flight when we stopped the timer,
        # so allow a single failure.
        bus = self.network.bus
        msg = bus.recv(TIMEOUT)
        if msg:
            self.assertIsNone(bus.recv(TIMEOUT))


class TestScanner(unittest.TestCase):

    def test_passive_scanning(self):
        scanner = canopen.network.NodeScanner()
        scanner.on_message_received(0x586)
        scanner.on_message_received(0x587)
        scanner.on_message_received(0x586)
        self.assertListEqual(scanner.nodes, [6, 7])


if __name__ == "__main__":
    unittest.main()
