import unittest

import canopen
from canopen.timestamp import TimeProducer


class TestTime(unittest.TestCase):

    def test_time_producer(self):
        network = canopen.Network()
        network.connect(interface="virtual", receive_own_messages=True)
        producer = TimeProducer(network)
        producer.transmit(1486236238)
        msg = network.bus.recv(1)
        network.disconnect()
        self.assertEqual(msg.arbitration_id, 0x100)
        self.assertEqual(msg.dlc, 6)
        self.assertEqual(msg.data, b"\xb0\xa4\x29\x04\x31\x43")


if __name__ == "__main__":
    unittest.main()
