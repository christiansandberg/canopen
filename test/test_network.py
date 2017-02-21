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


class TestScanner(unittest.TestCase):

    def test_passive_scanning(self):
        scanner = canopen.network.NodeScanner()
        scanner(can.Message(arbitration_id=0x586, extended_id=False))
        scanner(can.Message(arbitration_id=0x587, extended_id=False))
        scanner(can.Message(arbitration_id=0x586, extended_id=False))
        scanner(can.Message(arbitration_id=0x588, extended_id=True))
        self.assertListEqual(scanner.nodes, [6, 7])
