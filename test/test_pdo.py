import os.path
import unittest
from copy import deepcopy
import time
import canopen
from canopen.pdo import TPDO
import logging


SENDER_EDS_PATH = os.path.join(os.path.dirname(__file__), 'sender.eds')
RECEIVER_EDS_PATH = os.path.join(os.path.dirname(__file__), 'receiver.eds')


logging.basicConfig(level=logging.WARNING)


class TestPDO(unittest.TestCase):

    def setUp(self):
        self.network = canopen.Network()
        # Connect to a virtual network to allow for OS independent tests
        self.network.connect(channel="test", bustype="virtual",
                             receive_own_messages=True)
        self.sender_node = canopen.LocalNode(5, SENDER_EDS_PATH)
        self.sender_node.associate_network(self.network)
        self.receiver_node = canopen.LocalNode(6, RECEIVER_EDS_PATH)
        self.receiver_node.associate_network(self.network)

    def tearDown(self):
        self.sender_node.remove_network()
        self.receiver_node.remove_network()
        self.network.disconnect()

    def test_pdo_0x1800_settings(self):
        # Get the class global data
        sender_node = self.sender_node
        # Choose the first transmit PDO of the sender node
        send_pdo = sender_node.pdo[0x1800]

        # Check that the values are as specified in the EDS file
        self.assertEqual(send_pdo.com_index, 0x1800)
        self.assertEqual(send_pdo.map_index, 0x1A00)
        self.assertEqual(send_pdo.cob_id, 384 + send_pdo.pdo_node.node.id)
        self.assertEqual(send_pdo.trans_type, TPDO.TT_EVENT_TRIGGERED
                         | TPDO.TT_CYCLIC)
        self.assertEqual(send_pdo.inhibit_time.raw, 0)
        self.assertEqual(send_pdo.event_timer.raw, 100)

        # Careful: At the moment the length of the map is given in bytes, not
        # in bits!
        expected_map_values = [
            (0x6041, 0, 2),
        ]

        self.assertEqual(send_pdo.map, expected_map_values)

    def test_pdo_0x1803_settings(self):
        # Get the class global data
        sender_node = self.sender_node
        # Choose the first transmit PDO of the sender node
        pdo = sender_node.pdo[0x1803]

        # Check that the values are as specified in the EDS file
        self.assertEqual(pdo.com_index, 0x1803)
        self.assertEqual(pdo.map_index, 0x1A03)
        self.assertEqual(pdo.cob_id, 0x445)
        self.assertEqual(pdo.trans_type, TPDO.TT_SYNC_TRIGGERED
                         | TPDO.TT_CYCLIC)
        self.assertEqual(pdo.inhibit_time.raw, 0)
        self.assertEqual(pdo.event_timer.raw, 100)

        # Careful: At the moment the length of the map is given in bytes, not
        # in bits!
        expected_map_values = [
            (0x6041, 0, 2),
            (0x606c, 0, 4),
        ]

        self.assertEqual(pdo.map, expected_map_values)

    def test_pdo_0x1401_settings(self):
        # Get the class global data
        receiver_node = self.receiver_node
        # Choose the first transmit PDO of the sender node
        pdo = receiver_node.pdo[0x1401]

        # Check that the values are as specified in the EDS file
        self.assertEqual(pdo.com_index, 0x1401)
        self.assertEqual(pdo.map_index, 0x1601)
        self.assertEqual(pdo.cob_id, 768 + pdo.pdo_node.node.id)

        # Careful: At the moment the length of the map is given in bytes, not
        # in bits!
        expected_map_values = [
            (0x6040, 0, 2),
            (0x6060, 0, 1),
        ]

        self.assertEqual(pdo.map, expected_map_values)

    def test_pdo_0x1402_settings(self):
        # Get the class global data
        receiver_node = self.receiver_node
        # Choose the first transmit PDO of the sender node
        pdo = receiver_node.pdo[0x1402]

        # Check that the values are as specified in the EDS file
        self.assertEqual(pdo.com_index, 0x1402)
        self.assertEqual(pdo.map_index, 0x1602)
        self.assertEqual(pdo.cob_id, 0x422)

        # Careful: At the moment the length of the map is given in bytes, not
        # in bits!
        expected_map_values = [
            (0x6040, 0, 2),
            (0x607a, 0, 4),
        ]

        self.assertEqual(pdo.map, expected_map_values)

    def test_pdo_0x1402_reconfigure_mapping(self):
        # Helper function
        def set_mapping(map_entry, mapping):
            for map_subindex, (index, subindex, length) in enumerate(mapping,
                                                                     start=1):
                new_value = (index << 16) | (subindex << 8) | (length*8)
                map_entry[map_subindex].raw = new_value

        # Get the class global data
        receiver_node = self.receiver_node
        pdo = receiver_node.pdo[0x1402]
        # Create the new mapping data
        old_map = deepcopy(pdo.map)
        new_map = [
            (0x6660, 12, 4),
            (0x6661, 2, 1),
            (0x6662, 10, 2),
            (0x6663, 9, 2),
        ]
        wipe_out = [
            (0, 0, 0),
            (0, 0, 0),
            (0, 0, 0),
            (0, 0, 0),
        ]
        old_length = len(old_map)
        new_length = len(new_map)

        self.assertNotEqual(new_map, pdo.map)

        # Get the underlying object dictionary and make changes to it
        od = pdo.object_dictionary
        map_index = pdo.map_index
        map_entry = od[map_index]
        set_mapping(map_entry, new_map)
        map_entry[0].raw = new_length

        self.assertEqual(new_map, pdo.map)

        set_mapping(map_entry, wipe_out)
        map_entry[0].raw = new_length

        self.assertNotEqual(new_map, pdo.map)
        self.assertNotEqual(old_map, pdo.map)

        set_mapping(map_entry, old_map)
        map_entry[0].raw = old_length

        self.assertEqual(old_map, pdo.map)

    def test_pdo_0x1400_reconfigure_cobid(self):
        # Get the class global data
        receiver_node = self.receiver_node
        # Choose the first receive PDO (iterator style)
        pdo = receiver_node.pdo[0x1400]
        # Create the new mapping data
        old_cob_id = pdo.cob_id
        new_cob_id = old_cob_id + 1

        self.assertNotEqual(new_cob_id, pdo.cob_id)

        # Get the underlying object dictionary and make changes to it
        od = pdo.object_dictionary
        com_entry = od[pdo.com_index]
        com_entry['COB-ID'].raw = new_cob_id

        self.assertEqual(new_cob_id, pdo.cob_id)

        com_entry['COB-ID'].raw = old_cob_id

        self.assertEqual(old_cob_id, pdo.cob_id)

    def test_pdo_0x1801_reconfigure_cobid(self):
        # Get the class global data
        sender_node = self.sender_node
        # Choose the first receive PDO (iterator style)
        pdo = sender_node.pdo[0x1801]
        # Create the new mapping data
        old_cob_id = pdo.cob_id
        new_cob_id = old_cob_id + 1

        self.assertNotEqual(new_cob_id, pdo.cob_id)

        # Get the underlying object dictionary and make changes to it
        od = pdo.object_dictionary
        com_entry = od[pdo.com_index]
        com_entry['COB-ID'].raw = new_cob_id

        self.assertEqual(new_cob_id, pdo.cob_id)
        self.assertEqual(new_cob_id, pdo._task.msg.arbitration_id)

        com_entry['COB-ID'].raw = old_cob_id

        self.assertEqual(old_cob_id, pdo.cob_id)
        self.assertEqual(old_cob_id, pdo._task.msg.arbitration_id)

    def test_send_receive(self):
        # Get the class global data
        sender_node = self.sender_node
        receiver_node = self.receiver_node

        send_pdo = sender_node.pdo[0x1802]
        recv_pdo = None
        for rpdo in receiver_node.pdo.rx.values():
            if rpdo.cob_id == send_pdo.cob_id:
                recv_pdo = rpdo
                break

        self.assertIsNotNone(recv_pdo)
        # Assert that we have the correct mapping settings
        self.assertEqual(send_pdo.map[0], (0x6041, 0, 2))
        self.assertEqual(send_pdo.map[1], (0x6064, 0, 4))
        self.assertEqual(recv_pdo.map[0], (0x6040, 0, 2))
        self.assertEqual(recv_pdo.map[1], (0x607A, 0, 4))

        # Give the message a chance to be transmitted and received
        time.sleep(0.1)

        current_sender_values = [
            sender_node.get_value(0x6041),
            sender_node.get_value(0x6064)
        ]
        current_receiver_values = [
            receiver_node.get_value(0x6040),
            receiver_node.get_value(0x607A)
        ]

        self.assertEqual(current_sender_values, current_receiver_values)
        # Change the process data of the sender node
        old_sender_values = current_sender_values
        current_sender_values = [x+10 for x in old_sender_values]
        sender_node.set_value(0x6041, 0, current_sender_values[0])
        sender_node.set_value(0x6064, 0, current_sender_values[1])

        time.sleep(0.1)

        current_receiver_values = [
            receiver_node.get_value(0x6040),
            receiver_node.get_value(0x607A)
        ]

        self.assertNotEqual(old_sender_values, current_receiver_values)
        self.assertEqual(current_sender_values, current_receiver_values)

    def write_cbk(self, pdo):
        self.written[pdo.cob_id] = True

    def test_write_callback(self):
        self.written = {}
        # Get the class global data
        receiver_node = self.receiver_node
        recv_pdo = receiver_node.pdo[0x1403]
        recv_pdo.add_callback(self.write_cbk)

        time.sleep(0.12)

        self.assertIn(recv_pdo.cob_id, self.written)
        self.assertTrue(self.written)

        recv_pdo.remove_callback(self.write_cbk)
        self.written = {}

        time.sleep(0.12)

        self.assertNotIn(recv_pdo.cob_id, self.written)


if __name__ == "__main__":
    unittest.main()
