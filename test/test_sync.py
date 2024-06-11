import unittest

import canopen
from canopen.sync import SyncProducer


class TestSync(unittest.TestCase):

    def test_sync_producer(self):
        network = canopen.Network()
        network.connect(interface="virtual", receive_own_messages=True)
        producer = SyncProducer(network)
        producer.transmit()
        msg = network.bus.recv(1)
        network.disconnect()
        self.assertEqual(msg.arbitration_id, 0x80)
        self.assertEqual(msg.dlc, 0)

    def test_sync_producer_counter(self):
        network = canopen.Network()
        network.connect(interface="virtual", receive_own_messages=True)
        producer = SyncProducer(network)
        producer.transmit(2)
        msg = network.bus.recv(1)
        network.disconnect()
        self.assertEqual(msg.arbitration_id, 0x80)
        self.assertEqual(msg.dlc, 1)
        self.assertEqual(msg.data, b"\x02")


if __name__ == "__main__":
    unittest.main()
