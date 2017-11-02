import os
import unittest
import canopen
import logging

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

    @classmethod
    def tearDownClass(cls):
        cls.network1.disconnect()
        cls.network2.disconnect()

    def test_expedited_upload(self):
        self.local_node.sdo["Identity object"]["Vendor-ID"].raw = 0x99
        vendor_id = self.remote_node.sdo["Identity object"]["Vendor-ID"].raw
        self.assertEqual(vendor_id, 0x99)

    def test_segmented_upload(self):
        self.local_node.sdo["Manufacturer device name"].raw = "Some cool device"
        device_name = self.remote_node.sdo["Manufacturer device name"].data
        self.assertEqual(device_name, b"Some cool device")

    def test_expedited_download(self):
        self.remote_node.sdo["Identity object"]["Vendor-ID"].raw = 0xfeff
        vendor_id = self.local_node.sdo["Identity object"]["Vendor-ID"].raw
        self.assertEqual(vendor_id, 0xfeff)

    def test_segmented_upload(self):
        self.remote_node.sdo["Manufacturer device name"].raw = "Another cool device"
        device_name = self.local_node.sdo["Manufacturer device name"].data
        self.assertEqual(device_name, b"Another cool device")

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
            return b"\x01\x02"

    def test_callbacks(self):
        self.local_node.add_callback(self._some_callback)
        data = self.remote_node.sdo.upload(0x1003, 5)
        self.assertEqual(data, b"\x01\x02")
        self.assertEqual(self._kwargs["index"], 0x1003)
        self.assertEqual(self._kwargs["subindex"], 5)

        self.remote_node.sdo.download(0x1003, 6, b"\x03\x04")
        self.assertEqual(self._kwargs["data"], b"\x03\x04")


if __name__ == "__main__":
    unittest.main()
