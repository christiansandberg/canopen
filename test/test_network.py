import unittest
from threading import Event

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
        self.network.connect(
            interface="virtual",
            channel=1,
            receive_own_messages=True
        )
        self.addCleanup(self.network.disconnect)

        acc = []
        event = Event()

        def hook(_, data, ts):
            acc.append((data, ts))
            event.set()

        self.network.subscribe(COB_ID, hook)
        self.addCleanup(self.network.unsubscribe, COB_ID)

        task = self.network.send_periodic(COB_ID, DATA1, PERIOD)
        self.addCleanup(task.stop)

        event.wait(PERIOD*2)

        # Update task data.
        task.update(DATA2)
        event.clear()
        event.wait(PERIOD*2)
        task.stop()

        data = [v[0] for v in acc]
        self.assertEqual(data, [DATA1, DATA2])
        ts = [v[1] for v in acc]
        self.assertAlmostEqual(ts[1]-ts[0], PERIOD, places=1)


class TestScanner(unittest.TestCase):
    TIMEOUT = 0.1

    def setUp(self):
        self.scanner = canopen.network.NodeScanner()

    def test_scanner_on_message_received(self):
        self.scanner.on_message_received(0x081)
        # Emergency frames should be recognized.
        self.scanner.on_message_received(0x081)
        # Heartbeats should be recognized.
        self.scanner.on_message_received(0x703)
        # Tx PDOs should be recognized, but not Rx PDOs.
        self.scanner.on_message_received(0x185)
        self.scanner.on_message_received(0x206)
        self.scanner.on_message_received(0x287)
        self.scanner.on_message_received(0x308)
        self.scanner.on_message_received(0x389)
        self.scanner.on_message_received(0x40a)
        self.scanner.on_message_received(0x48b)
        self.scanner.on_message_received(0x50c)
        # SDO responses from .search() should be recognized,
        # but not SDO requests.
        self.scanner.on_message_received(0x58d)
        self.scanner.on_message_received(0x50e)
        self.assertListEqual(self.scanner.nodes, [1, 3, 5, 7, 9, 11, 13])

    def test_scanner_reset(self):
        self.scanner.nodes = [1, 2, 3]  # Mock scan.
        self.scanner.reset()
        self.assertListEqual(self.scanner.nodes, [])

    def test_scanner_search_no_network(self):
        with self.assertRaisesRegex(RuntimeError, "Network is required"):
            self.scanner.search()

    def test_scanner_search(self):
        bus = can.Bus(
            interface="virtual",
            channel="test",
            receive_own_messages=True,
        )
        net = canopen.Network(bus)
        net.connect()
        self.addCleanup(net.disconnect)

        scanner = canopen.network.NodeScanner(net)
        scanner.search()

        payload = bytes([64, 0, 16, 0, 0, 0, 0, 0])
        acc = [bus.recv(self.TIMEOUT) for _ in range(127)]
        for node_id, msg in enumerate(acc, start=1):
            with self.subTest(node_id=node_id):
                self.assertIsNotNone(msg)
                self.assertEqual(msg.arbitration_id, 0x600 + node_id)
                self.assertEqual(msg.data, payload)
        # Check that no spurious packets were sent.
        self.assertIsNone(bus.recv(self.TIMEOUT))

    def test_scanner_search_limit(self):
        bus = can.Bus(
            interface="virtual",
            channel="test",
            receive_own_messages=True,
        )
        net = canopen.Network(bus)
        net.connect()
        self.addCleanup(net.disconnect)

        scanner = canopen.network.NodeScanner(net)
        scanner.search(limit=1)
        msg = bus.recv(self.TIMEOUT)
        self.assertIsNotNone(msg)
        self.assertEqual(msg.arbitration_id, 0x601)
        # Check that no spurious packets were sent.
        self.assertIsNone(bus.recv(self.TIMEOUT))


if __name__ == "__main__":
    unittest.main()
