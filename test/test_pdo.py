import os.path
import unittest
import canopen

EDS_PATH = os.path.join(os.path.dirname(__file__), 'sample.eds')


class TestPDO(unittest.TestCase):

    def test_bit_mapping(self):
        node = canopen.Node(1, EDS_PATH)
        map = node.pdo.tx[1]
        map.add_variable('INTEGER16 value')  # 0x2001
        map.add_variable('UNSIGNED8 value', length=4)  # 0x2002
        map.add_variable('INTEGER8 value', length=4)  # 0x2003
        map.add_variable('INTEGER32 value')  # 0x2004
        map.add_variable('BOOLEAN value', length=1)  # 0x2005
        map.add_variable('BOOLEAN value 2', length=1)  # 0x2006

        # Write some values
        map['INTEGER16 value'].raw = -3
        map['UNSIGNED8 value'].raw = 0xf
        map['INTEGER8 value'].raw = -2
        map['INTEGER32 value'].raw = 0x01020304
        map['BOOLEAN value'].raw = False
        map['BOOLEAN value 2'].raw = True

        # Check expected data
        self.assertEqual(map.data, b'\xfd\xff\xef\x04\x03\x02\x01\x02')

        # Read values from data
        self.assertEqual(map['INTEGER16 value'].raw, -3)
        self.assertEqual(map['UNSIGNED8 value'].raw, 0xf)
        self.assertEqual(map['INTEGER8 value'].raw, -2)
        self.assertEqual(map['INTEGER32 value'].raw, 0x01020304)
        self.assertEqual(map['BOOLEAN value'].raw, False)
        self.assertEqual(map['BOOLEAN value 2'].raw, True)

        self.assertEqual(node.tpdo[1]['INTEGER16 value'].raw, -3)
        self.assertEqual(node.tpdo[1]['UNSIGNED8 value'].raw, 0xf)
        self.assertEqual(node.tpdo[1]['INTEGER8 value'].raw, -2)
        self.assertEqual(node.tpdo[1]['INTEGER32 value'].raw, 0x01020304)
        self.assertEqual(node.tpdo['INTEGER32 value'].raw, 0x01020304)
        self.assertEqual(node.tpdo[1]['BOOLEAN value'].raw, False)
        self.assertEqual(node.tpdo[1]['BOOLEAN value 2'].raw, True)

        # Test different types of access
        self.assertEqual(node.pdo[0x1600]['INTEGER16 value'].raw, -3)
        self.assertEqual(node.pdo['INTEGER16 value'].raw, -3)
        self.assertEqual(node.pdo.tx[1]['INTEGER16 value'].raw, -3)
        self.assertEqual(node.pdo[0x2001].raw, -3)
        self.assertEqual(node.tpdo[0x2001].raw, -3)
        self.assertEqual(node.pdo[0x2002].raw, 0xf)
        self.assertEqual(node.pdo['0x2002'].raw, 0xf)
        self.assertEqual(node.tpdo[0x2002].raw, 0xf)
        self.assertEqual(node.pdo[0x1600][0x2002].raw, 0xf)

    def test_bit_offsets(self):
        node = canopen.Node(1, EDS_PATH)
        pdo = node.pdo.tx[1]
        pdo.add_variable('UNSIGNED8 value', length=4)  # byte-aligned, partial byte length
        pdo.add_variable('INTEGER8 value')  # non-byte-aligned, one whole byte length
        pdo.add_variable('UNSIGNED32 value', length=24)  # non-aligned, partial last byte
        pdo.add_variable('UNSIGNED16 value', length=12)  # non-aligned, whole last byte
        pdo.add_variable('INTEGER16 value', length=3)  # byte-aligned, partial byte length
        pdo.add_variable('INTEGER32 value', length=13)  # non-aligned, whole last byte

        # Write some values
        pdo['UNSIGNED8 value'].raw = 3
        pdo['INTEGER8 value'].raw = -2
        pdo['UNSIGNED32 value'].raw = 0x987654
        pdo['UNSIGNED16 value'].raw = 0x321
        pdo['INTEGER16 value'].raw = -1
        pdo['INTEGER32 value'].raw = -1071

        # Check expected data
        self.assertEqual(pdo.data, b'\xe3\x4f\x65\x87\x19\x32\x8f\xde')

        # Read values from data
        self.assertEqual(pdo['UNSIGNED8 value'].raw, 3)
        self.assertEqual(pdo['INTEGER8 value'].raw, -2)
        self.assertEqual(pdo['UNSIGNED32 value'].raw, 0x987654)
        self.assertEqual(pdo['UNSIGNED16 value'].raw, 0x321)
        self.assertEqual(pdo['INTEGER16 value'].raw, -1)
        self.assertEqual(pdo['INTEGER32 value'].raw, -1071)

    def test_save_pdo(self):
        node = canopen.Node(1, EDS_PATH)
        node.tpdo.save()
        node.rpdo.save()


if __name__ == "__main__":
    unittest.main()
