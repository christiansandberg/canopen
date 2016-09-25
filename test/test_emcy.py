import unittest
from canopen import emcy


class TestEmcy(unittest.TestCase):

    def test_emcy_list(self):
        emcy_node = emcy.EmcyConsumer()
        emcy_node.on_emcy(0x81, b'\x01\x20\x02\x00\x01\x02\x03\x04', 1473418396.0)
        emcy_node.on_emcy(0x81, b'\x10\x90\x01\x00\x01\x02\x03\x04', 1473418397.0)

        self.assertEqual(len(emcy_node.log), 2)
        self.assertEqual(len(emcy_node.active), 2)

        error = emcy_node.log[0]
        self.assertIsInstance(error, emcy.EmcyError)
        self.assertIsInstance(error, Exception)
        self.assertEqual(error.code, 0x2001)
        self.assertEqual(error.register, 0x02)
        self.assertEqual(error.data, b'\x00\x01\x02\x03\x04')
        self.assertAlmostEqual(error.timestamp, 1473418396.0)
        self.assertEqual(emcy_node.active[0], error)

        error = emcy_node.log[1]
        self.assertEqual(error.code, 0x9010)
        self.assertEqual(error.register, 0x01)
        self.assertEqual(error.data, b'\x00\x01\x02\x03\x04')
        self.assertAlmostEqual(error.timestamp, 1473418397.0)
        self.assertEqual(emcy_node.active[1], error)

        emcy_node.on_emcy(0x81, b'\x00\x00\x00\x00\x00\x00\x00\x00', 1473418397.0)
        self.assertEqual(len(emcy_node.log), 2)
        self.assertEqual(len(emcy_node.active), 0)

    def test_str(self):
        error = emcy.EmcyError(0x2001, 0x02, b'\x00\x01\x02\x03\x04', 1473418396.0)
        self.assertEqual(str(error), "Code 0x2001, Current")

        error = emcy.EmcyError(0x50FF, 0x01, b'\x00\x01\x02\x03\x04', 1473418396.0)
        self.assertEqual(str(error), "Code 0x50FF, Device Hardware")

        error = emcy.EmcyError(0x7100, 0x01, b'\x00\x01\x02\x03\x04', 1473418396.0)
        self.assertEqual(str(error), "Code 0x7100")
