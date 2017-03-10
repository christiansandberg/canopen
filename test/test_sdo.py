import os
import unittest
import canopen


EDS_PATH = os.path.join(os.path.dirname(__file__), 'sample.eds')


class TestSDO(unittest.TestCase):
    """
    Test SDO traffic by example. Most are taken from
    http://www.canopensolutions.com/english/about_canopen/device_configuration_canopen.shtml
    """

    def _send_message(self, can_id, data, remote=False):
        """Will be used instead of the usual Network.send_message method.

        Checks that the message data is according to expected and answers
        with the provided data.
        """
        print("%r" % data)
        self.assertSequenceEqual(data, self.data.pop(0))
        self.assertEqual(can_id, 0x602)
        self.network.notify(0x582, self.data.pop(0), 0.0)

    def setUp(self):
        network = canopen.Network()
        network.send_message = self._send_message
        node = network.add_node(2, EDS_PATH)
        node.sdo.RESPONSE_TIMEOUT = 0.01
        self.network = network

    def test_expedited_upload(self):
        self.data = [
            b'\x40\x18\x10\x01\x00\x00\x00\x00',
            b'\x43\x18\x10\x01\x04\x00\x00\x00'
        ]
        vendor_id = self.network[2].sdo[0x1018][1].raw
        self.assertEqual(vendor_id, 4)

        # UNSIGNED8 without padded data part (see issue #5)
        self.data = [
            b'\x40\x00\x14\x02\x00\x00\x00\x00',
            b'\x4f\x00\x14\x02\xfe'
        ]
        trans_type = self.network[2].sdo[0x1400]['Transmission type RPDO 1'].raw
        self.assertEqual(trans_type, 254)

    def test_expedited_download(self):
        self.data = [
            b'\x2b\x17\x10\x00\xa0\x0f\x00\x00',
            b'\x60\x17\x10\x00\x00\x00\x00\x00'
        ]
        self.network[2].sdo[0x1017].raw = 4000

    def test_segmented_upload(self):
        self.data = [
            b'\x40\x08\x10\x00\x00\x00\x00\x00',
            b'\x41\x08\x10\x00\x1A\x00\x00\x00',
            b'\x60\x00\x00\x00\x00\x00\x00\x00',
            b'\x00\x54\x69\x6E\x79\x20\x4E\x6F',
            b'\x70\x00\x00\x00\x00\x00\x00\x00',
            b'\x10\x64\x65\x20\x2D\x20\x4D\x65',
            b'\x60\x00\x00\x00\x00\x00\x00\x00',
            b'\x00\x67\x61\x20\x44\x6F\x6D\x61',
            b'\x70\x00\x00\x00\x00\x00\x00\x00',
            b'\x15\x69\x6E\x73\x20\x21\x00\x00'
        ]
        device_name = self.network[2].sdo[0x1008].raw
        self.assertEqual(device_name, "Tiny Node - Mega Domains !")

    def test_segmented_download(self):
        self.data = [
            b'\x21\x00\x20\x00\x0d\x00\x00\x00',
            b'\x60\x00\x20\x00\x00\x00\x00\x00',
            b'\x00\x41\x20\x6c\x6f\x6e\x67\x20',
            b'\x20\x00\x20\x00\x00\x00\x00\x00',
            b'\x13\x73\x74\x72\x69\x6e\x67\x00',
            b'\x30\x00\x20\x00\x00\x00\x00\x00'
        ]
        self.network[2].sdo['Writable string'].raw = 'A long string'

    def test_writable_file(self):
        self.data = [
            b'\x20\x00\x20\x00\x00\x00\x00\x00',
            b'\x60\x00\x20\x00\x00\x00\x00\x00',
            b'\x00\x31\x32\x33\x34\x35\x36\x37',
            b'\x20\x00\x20\x00\x00\x00\x00\x00',
            b'\x1a\x38\x39\x00\x00\x00\x00\x00',
            b'\x30\x00\x20\x00\x00\x00\x00\x00',
            b'\x0f\x00\x00\x00\x00\x00\x00\x00',
            b'\x20\x00\x20\x00\x00\x00\x00\x00'
        ]
        fp = self.network[2].sdo['Writable string'].open('wb')
        fp.write(b'1234')
        fp.write(b'56789')
        fp.close()
        self.assertTrue(fp.closed)
        # Write on closed file
        with self.assertRaises(ValueError):
            fp.write(b'123')

    def test_abort(self):
        self.data = [
            b'\x40\x18\x10\x01\x00\x00\x00\x00',
            b'\x80\x18\x10\x01\x11\x00\x09\x06'
        ]
        with self.assertRaises(canopen.SdoAbortedError) as cm:
            vendor_id = self.network[2].sdo[0x1018][1].raw
        self.assertEqual(cm.exception.code, 0x06090011)


if __name__ == "__main__":
    unittest.main()
