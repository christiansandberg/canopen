import os
import unittest
import canopen
import logging
import time

# logging.basicConfig(level=logging.DEBUG)

EDS_PATH = os.path.join(os.path.dirname(__file__), 'sample.eds')


class TestSDO(unittest.TestCase):
    """
    Test SDO client and server against each other.
    """

    @classmethod
    def setUpClass(cls):
        cls.network1 = canopen.Network()
        cls.network1.connect("test", bustype="virtual")
        cls.remote_node = cls.network1.add_node(2, EDS_PATH)

        cls.network2 = canopen.Network()
        cls.network2.connect("test", bustype="virtual")
        cls.local_node = cls.network2.create_node(2, EDS_PATH)

        cls.remote_node2 = cls.network1.add_node(3, EDS_PATH)

        cls.local_node2 = cls.network2.create_node(3, EDS_PATH)

    @classmethod
    def tearDownClass(cls):
        cls.network1.disconnect()
        cls.network2.disconnect()

    def test_expedited_upload(self):
        self.local_node.sdo[0x1400][1].raw = 0x99
        vendor_id = self.remote_node.sdo[0x1400][1].raw
        self.assertEqual(vendor_id, 0x99)

    def test_block_upload_switch_to_expedite_upload(self):
        with self.assertRaises(canopen.SdoCommunicationError) as context:
            with self.remote_node.sdo[0x1008].open('r', block_transfer=True) as fp:
                pass
        # We get this since the sdo client don't support the switch
        # from block upload to expedite upload
        self.assertEqual("Unexpected response 0x41", str(context.exception))

    def test_block_download_not_supported(self):
        data = b"TEST DEVICE"
        with self.assertRaises(canopen.SdoAbortedError) as context:
            with self.remote_node.sdo[0x1008].open('wb',
                                                   size=len(data),
                                                   block_transfer=True) as fp:
                pass
        self.assertEqual(context.exception.code, 0x05040001)

    def test_expedited_upload_default_value_visible_string(self):
        device_name = self.remote_node.sdo["Manufacturer device name"].raw
        self.assertEqual(device_name, "TEST DEVICE")

    def test_expedited_upload_default_value_real(self):
        sampling_rate = self.remote_node.sdo["Sensor Sampling Rate (Hz)"].raw
        self.assertAlmostEqual(sampling_rate, 5.2, places=2)

    def test_segmented_upload(self):
        self.local_node.sdo["Manufacturer device name"].raw = "Some cool device"
        device_name = self.remote_node.sdo["Manufacturer device name"].data
        self.assertEqual(device_name, b"Some cool device")

    def test_expedited_download(self):
        self.remote_node.sdo[0x2004].raw = 0xfeff
        value = self.local_node.sdo[0x2004].raw
        self.assertEqual(value, 0xfeff)

    def test_expedited_download_wrong_datatype(self):
        # Try to write 32 bit in integer16 type
        with self.assertRaises(canopen.SdoAbortedError) as error:
            self.remote_node.sdo.download(0x2001, 0x0, bytes([10, 10, 10, 10]))
        self.assertEqual(error.exception.code, 0x06070010)
        # Try to write normal 16 bit word, should be ok
        self.remote_node.sdo.download(0x2001, 0x0, bytes([10, 10]))
        value = self.remote_node.sdo.upload(0x2001, 0x0)
        self.assertEqual(value, bytes([10, 10]))

    def test_segmented_download(self):
        self.remote_node.sdo[0x2000].raw = "Another cool device"
        value = self.local_node.sdo[0x2000].data
        self.assertEqual(value, b"Another cool device")

    def test_slave_send_heartbeat(self):
        # Setting the heartbeat time should trigger hearbeating
        # to start
        self.remote_node.sdo["Producer heartbeat time"].raw = 1000
        state = self.remote_node.nmt.wait_for_heartbeat()
        self.local_node.nmt.stop_heartbeat()
        # The NMT master will change the state INITIALISING (0)
        # to PRE-OPERATIONAL (127)
        self.assertEqual(state, 'PRE-OPERATIONAL')

    def test_nmt_state_initializing_to_preoper(self):
        # Initialize the heartbeat timer
        self.local_node.sdo["Producer heartbeat time"].raw = 1000
        self.local_node.nmt.stop_heartbeat()
        # This transition shall start the heartbeating
        self.local_node.nmt.state = 'INITIALISING'
        self.local_node.nmt.state = 'PRE-OPERATIONAL'
        state = self.remote_node.nmt.wait_for_heartbeat()
        self.local_node.nmt.stop_heartbeat()
        self.assertEqual(state, 'PRE-OPERATIONAL')

    def test_receive_abort_request(self):
        self.remote_node.sdo.abort(0x05040003)
        # Line below is just so that we are sure the client have received the abort
        # before we do the check
        time.sleep(0.1)
        self.assertEqual(self.local_node.sdo.last_received_error, 0x05040003)

    def test_start_remote_node(self):
        self.remote_node.nmt.state = 'OPERATIONAL'
        # Line below is just so that we are sure the client have received the command
        # before we do the check
        time.sleep(0.1)
        slave_state = self.local_node.nmt.state
        self.assertEqual(slave_state, 'OPERATIONAL')

    def test_two_nodes_on_the_bus(self):
        self.local_node.sdo["Manufacturer device name"].raw = "Some cool device"
        device_name = self.remote_node.sdo["Manufacturer device name"].data
        self.assertEqual(device_name, b"Some cool device")

        self.local_node2.sdo["Manufacturer device name"].raw = "Some cool device2"
        device_name = self.remote_node2.sdo["Manufacturer device name"].data
        self.assertEqual(device_name, b"Some cool device2")

    def test_abort(self):
        with self.assertRaises(canopen.SdoAbortedError) as cm:
            _ = self.remote_node.sdo.upload(0x1234, 0)
        # Should be Object does not exist
        self.assertEqual(cm.exception.code, 0x06020000)

        with self.assertRaises(canopen.SdoAbortedError) as cm:
            _ = self.remote_node.sdo.upload(0x1018, 100)
        # Should be Subindex does not exist
        self.assertEqual(cm.exception.code, 0x06090011)

        with self.assertRaises(canopen.SdoAbortedError) as cm:
            _ = self.remote_node.sdo[0x1001].data
        # Should be Resource not available
        self.assertEqual(cm.exception.code, 0x060A0023)

    def _some_read_callback(self, **kwargs):
        self._kwargs = kwargs
        if kwargs["index"] == 0x1003:
            return 0x0201

    def _some_write_callback(self, **kwargs):
        self._kwargs = kwargs

    def test_callbacks(self):
        self.local_node.add_read_callback(self._some_read_callback)
        self.local_node.add_write_callback(self._some_write_callback)

        data = self.remote_node.sdo.upload(0x1003, 5)
        self.assertEqual(data, b"\x01\x02\x00\x00")
        self.assertEqual(self._kwargs["index"], 0x1003)
        self.assertEqual(self._kwargs["subindex"], 5)

        self.remote_node.sdo.download(0x1017, 0, b"\x03\x04")
        self.assertEqual(self._kwargs["index"], 0x1017)
        self.assertEqual(self._kwargs["subindex"], 0)
        self.assertEqual(self._kwargs["data"], b"\x03\x04")


class TestNMT(unittest.TestCase):
    """
    Test NMT slave.
    """

    @classmethod
    def setUpClass(cls):
        cls.network1 = canopen.Network()
        cls.network1.connect("test", bustype="virtual")
        cls.remote_node = cls.network1.add_node(2, EDS_PATH)

        cls.network2 = canopen.Network()
        cls.network2.connect("test", bustype="virtual")
        cls.local_node = cls.network2.create_node(2, EDS_PATH)

        cls.remote_node2 = cls.network1.add_node(3, EDS_PATH)

        cls.local_node2 = cls.network2.create_node(3, EDS_PATH)

    @classmethod
    def tearDownClass(cls):
        cls.network1.disconnect()
        cls.network2.disconnect()

    def test_start_two_remote_nodes(self):
        self.remote_node.nmt.state = 'OPERATIONAL'
        # Line below is just so that we are sure the client have received the command
        # before we do the check
        time.sleep(0.1)
        slave_state = self.local_node.nmt.state
        self.assertEqual(slave_state, 'OPERATIONAL')

        self.remote_node2.nmt.state = 'OPERATIONAL'
        # Line below is just so that we are sure the client have received the command
        # before we do the check
        time.sleep(0.1)
        slave_state = self.local_node2.nmt.state
        self.assertEqual(slave_state, 'OPERATIONAL')

    def test_stop_two_remote_nodes_using_broadcast(self):
        # This is a NMT broadcast "Stop remote node"
        # ie. set the node in STOPPED state
        self.network1.send_message(0, [2, 0])

        # Line below is just so that we are sure the slaves have received the command
        # before we do the check
        time.sleep(0.1)
        slave_state = self.local_node.nmt.state
        self.assertEqual(slave_state, 'STOPPED')
        slave_state = self.local_node2.nmt.state
        self.assertEqual(slave_state, 'STOPPED')

    def test_heartbeat(self):
        # self.assertEqual(self.remote_node.nmt.state, 'INITIALISING')
        # self.assertEqual(self.local_node.nmt.state, 'INITIALISING')
        self.local_node.nmt.state = 'OPERATIONAL'
        self.local_node.sdo[0x1017].raw = 100
        time.sleep(0.2)
        self.assertEqual(self.remote_node.nmt.state, 'OPERATIONAL')

        self.local_node.nmt.stop_heartbeat()

class TestPDO(unittest.TestCase):
    """
    Test PDO slave.
    """

    @classmethod
    def setUpClass(cls):
        cls.network1 = canopen.Network()
        cls.network1.connect("test", bustype="virtual")
        cls.remote_node = cls.network1.add_node(2, EDS_PATH)

        cls.network2 = canopen.Network()
        cls.network2.connect("test", bustype="virtual")
        cls.local_node = cls.network2.create_node(2, EDS_PATH)

    @classmethod
    def tearDownClass(cls):
        cls.network1.disconnect()
        cls.network2.disconnect()

    def test_read(self):
        # TODO: Do some more checks here. Currently it only tests that they
        # can be called without raising an error.
        self.remote_node.pdo.read()
        self.local_node.pdo.read()

    def test_save(self):
        # TODO: Do some more checks here. Currently it only tests that they
        # can be called without raising an error.
        self.remote_node.pdo.save()
        self.local_node.pdo.save()


if __name__ == "__main__":
    unittest.main()
