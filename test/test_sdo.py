import os
import unittest
# import binascii
import canopen

EDS_PATH = os.path.join(os.path.dirname(__file__), 'sample.eds')

TX = 1
RX = 2


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
        next_data = self.data.pop(0)
        self.assertEqual(next_data[0], TX, "No transmission was expected")
        # print("> %s (%s)" % (binascii.hexlify(data), binascii.hexlify(next_data[1])))
        self.assertSequenceEqual(data, next_data[1])
        self.assertEqual(can_id, 0x602)
        while self.data and self.data[0][0] == RX:
            # print("< %s" % binascii.hexlify(self.data[0][1]))
            self.network.notify(0x582, self.data.pop(0)[1], 0.0)

    def setUp(self):
        network = canopen.Network()
        network.send_message = self._send_message
        node = network.add_node(2, EDS_PATH)
        node.sdo.RESPONSE_TIMEOUT = 0.01
        self.network = network

    def test_expedited_upload(self):
        self.data = [
            (TX, b'\x40\x18\x10\x01\x00\x00\x00\x00'),
            (RX, b'\x43\x18\x10\x01\x04\x00\x00\x00')
        ]
        vendor_id = self.network[2].sdo[0x1018][1].raw
        self.assertEqual(vendor_id, 4)

        # UNSIGNED8 without padded data part (see issue #5)
        self.data = [
            (TX, b'\x40\x00\x14\x02\x00\x00\x00\x00'),
            (RX, b'\x4f\x00\x14\x02\xfe')
        ]
        trans_type = self.network[2].sdo[0x1400]['Transmission type RPDO 1'].raw
        self.assertEqual(trans_type, 254)

    def test_size_not_specified(self):
        self.data = [
            (TX, b'\x40\x00\x14\x02\x00\x00\x00\x00'),
            (RX, b'\x42\x00\x14\x02\xfe\x00\x00\x00')
        ]
        # Make sure the size of the data is 1 byte
        data = self.network[2].sdo.upload(0x1400, 2)
        self.assertEqual(data, b'\xfe')

    def test_expedited_download(self):
        self.data = [
            (TX, b'\x2b\x17\x10\x00\xa0\x0f\x00\x00'),
            (RX, b'\x60\x17\x10\x00\x00\x00\x00\x00')
        ]
        self.network[2].sdo[0x1017].raw = 4000

    def test_segmented_upload(self):
        self.data = [
            (TX, b'\x40\x08\x10\x00\x00\x00\x00\x00'),
            (RX, b'\x41\x08\x10\x00\x1A\x00\x00\x00'),
            (TX, b'\x60\x00\x00\x00\x00\x00\x00\x00'),
            (RX, b'\x00\x54\x69\x6E\x79\x20\x4E\x6F'),
            (TX, b'\x70\x00\x00\x00\x00\x00\x00\x00'),
            (RX, b'\x10\x64\x65\x20\x2D\x20\x4D\x65'),
            (TX, b'\x60\x00\x00\x00\x00\x00\x00\x00'),
            (RX, b'\x00\x67\x61\x20\x44\x6F\x6D\x61'),
            (TX, b'\x70\x00\x00\x00\x00\x00\x00\x00'),
            (RX, b'\x15\x69\x6E\x73\x20\x21\x00\x00')
        ]
        device_name = self.network[2].sdo[0x1008].raw
        self.assertEqual(device_name, "Tiny Node - Mega Domains !")

    def test_segmented_download(self):
        self.data = [
            (TX, b'\x21\x00\x20\x00\x0d\x00\x00\x00'),
            (RX, b'\x60\x00\x20\x00\x00\x00\x00\x00'),
            (TX, b'\x00\x41\x20\x6c\x6f\x6e\x67\x20'),
            (RX, b'\x20\x00\x20\x00\x00\x00\x00\x00'),
            (TX, b'\x13\x73\x74\x72\x69\x6e\x67\x00'),
            (RX, b'\x30\x00\x20\x00\x00\x00\x00\x00')
        ]
        self.network[2].sdo['Writable string'].raw = 'A long string'

    def test_block_download(self):
        self.data = [
            (TX, b'\xc6\x00\x20\x00\x1e\x00\x00\x00'),
            (RX, b'\xa4\x00\x20\x00\x7f\x00\x00\x00'),
            (TX, b'\x01\x41\x20\x72\x65\x61\x6c\x6c'),
            (TX, b'\x02\x79\x20\x72\x65\x61\x6c\x6c'),
            (TX, b'\x03\x79\x20\x6c\x6f\x6e\x67\x20'),
            (TX, b'\x04\x73\x74\x72\x69\x6e\x67\x2e'),
            (TX, b'\x85\x2e\x2e\x00\x00\x00\x00\x00'),
            (RX, b'\xa2\x05\x7f\x00\x00\x00\x00\x00'),
            (TX, b'\xd5\x45\x69\x00\x00\x00\x00\x00'),
            (RX, b'\xa1\x00\x00\x00\x00\x00\x00\x00')
        ]
        data = b'A really really long string...'
        with self.network[2].sdo['Writable string'].open(
            'wb', size=len(data), block_transfer=True) as fp:
            fp.write(data)

    def test_block_upload(self):
        self.data = [
            (TX, b'\xa4\x08\x10\x00\x7f\x00\x00\x00'),
            (RX, b'\xc6\x08\x10\x00\x1a\x00\x00\x00'),
            (TX, b'\xa3\x00\x00\x00\x00\x00\x00\x00'),
            (RX, b'\x01\x54\x69\x6e\x79\x20\x4e\x6f'),
            (RX, b'\x02\x64\x65\x20\x2d\x20\x4d\x65'),
            (RX, b'\x03\x67\x61\x20\x44\x6f\x6d\x61'),
            (RX, b'\x84\x69\x6e\x73\x20\x21\x00\x00'),
            (TX, b'\xa2\x04\x7f\x00\x00\x00\x00\x00'),
            (RX, b'\xc9\x40\xe1\x00\x00\x00\x00\x00'),
            (TX, b'\xa1\x00\x00\x00\x00\x00\x00\x00')
        ]
        with self.network[2].sdo[0x1008].open('r', block_transfer=True) as fp:
            data = fp.read()
        self.assertEqual(data, 'Tiny Node - Mega Domains !')

    def test_writable_file(self):
        self.data = [
            (TX, b'\x20\x00\x20\x00\x00\x00\x00\x00'),
            (RX, b'\x60\x00\x20\x00\x00\x00\x00\x00'),
            (TX, b'\x00\x31\x32\x33\x34\x35\x36\x37'),
            (RX, b'\x20\x00\x20\x00\x00\x00\x00\x00'),
            (TX, b'\x1a\x38\x39\x00\x00\x00\x00\x00'),
            (RX, b'\x30\x00\x20\x00\x00\x00\x00\x00'),
            (TX, b'\x0f\x00\x00\x00\x00\x00\x00\x00'),
            (RX, b'\x20\x00\x20\x00\x00\x00\x00\x00')
        ]
        with self.network[2].sdo['Writable string'].open('wb') as fp:
            fp.write(b'1234')
            fp.write(b'56789')
        self.assertTrue(fp.closed)
        # Write on closed file
        with self.assertRaises(ValueError):
            fp.write(b'123')

    def test_abort(self):
        self.data = [
            (TX, b'\x40\x18\x10\x01\x00\x00\x00\x00'),
            (RX, b'\x80\x18\x10\x01\x11\x00\x09\x06')
        ]
        with self.assertRaises(canopen.SdoAbortedError) as cm:
            _ = self.network[2].sdo[0x1018][1].raw
        self.assertEqual(cm.exception.code, 0x06090011)

    def test_add_sdo_channel(self):
        client = self.network[2].add_sdo(0x123456, 0x234567)
        self.assertIn(client, self.network[2].sdo_channels)


if __name__ == "__main__":
    unittest.main()
