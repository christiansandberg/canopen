import os
import unittest
import canopen
import logging

logging.basicConfig(level=logging.DEBUG)


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
            self.remote_node.sdo[0x1008].open('r', block_transfer=True)
        # We get this since the sdo client don't support the switch
        # from block upload to expedite upload
        self.assertTrue("Unexpected response 0x41" in context.exception)

    def test_block_download_not_supported(self):
        data = b"TEST DEVICE"
        with self.assertRaises(canopen.SdoAbortedError) as context:
            self.remote_node.sdo[0x1008].open('wb',
                                              size=len(data),
                                              block_transfer=True)
        self.assertEqual(context.exception.code, 0x05040001)

    def test_expedited_upload_default_value_visible_string(self):
        device_name = self.remote_node.sdo["Manufacturer device name"].raw
        self.assertEqual(device_name, b"TEST DEVICE")

    def test_expedited_upload_default_value_real(self):
        sampling_rate = self.remote_node.sdo["Sensor Sampling Rate (Hz)"].raw
        self.assertAlmostEqual(sampling_rate, 5.2, places=2)

    def test_segmented_upload(self):
        self.local_node.sdo["Manufacturer device name"].raw = "Some cool device"
        device_name = self.remote_node.sdo["Manufacturer device name"].data
        self.assertEqual(device_name, b"Some cool device")

    def test_expedited_download(self):
        self.remote_node.sdo["Identity object"]["Vendor-ID"].raw = 0xfeff
        vendor_id = self.local_node.sdo["Identity object"]["Vendor-ID"].raw
        self.assertEqual(vendor_id, 0xfeff)

    def test_segmented_download(self):
        self.remote_node.sdo["Manufacturer device name"].raw = "Another cool device"
        device_name = self.local_node.sdo["Manufacturer device name"].data
        self.assertEqual(device_name, b"Another cool device")

    def test_slave_send_heartbeat(self):
        # Setting the heartbeat time should trigger hearbeating 
        # to start
        self.remote_node.sdo["Producer heartbeat time"].raw = 1000
        state = self.remote_node.nmt.wait_for_heartbeat()
        self.local_node.nmt.stop_heartbeat()
        # The NMT master will change the state INITIALISING (0)
        # to PRE-OPERATIONAL (127)
        self.assertEqual(state, canopen.nmt.NMT_STATES[127])

    def test_receive_abort_request(self):
        self.remote_node.sdo.abort(0x05040003)
        # Line below is just so that we are sure the client have received the abort
        # before we do the check
        self.remote_node.sdo["Manufacturer device name"].raw = "Another cool device"
        self.assertEqual(self.local_node.sdo.last_received_error, 0x05040003)

    def test_abort(self):
        with self.assertRaises(canopen.SdoAbortedError) as cm:
            _ = self.remote_node.sdo.upload(0x1234, 0)
        # Should be Object does not exist
        self.assertEqual(cm.exception.code, 0x06020000)

        with self.assertRaises(canopen.SdoAbortedError) as cm:
            _ = self.remote_node.sdo.upload(0x1018, 100)
        # Should be Subindex does not exist
        self.assertEqual(cm.exception.code, 0x06090011)

    def _some_callback(self, **kwargs):
        self._kwargs = kwargs
        if kwargs["index"] == 0x1003:
            return 0x0201

    def test_callbacks(self):
        self.local_node.add_callback(self._some_callback)
        data = self.remote_node.sdo.upload(0x1003, 5)
        self.assertEqual(data, b"\x01\x02\x00\x00")
        self.assertEqual(self._kwargs["index"], 0x1003)
        self.assertEqual(self._kwargs["subindex"], 5)

        self.remote_node.sdo.download(0x1003, 6, b"\x03\x04\x05\x06")
        self.assertEqual(self._kwargs["data"], b"\x03\x04\x05\x06")


if __name__ == "__main__":
    unittest.main()
