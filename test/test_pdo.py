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
        map['INTEGER16 value'].set_raw(-3)
        map['UNSIGNED8 value'].set_raw(0xf)
        map['INTEGER8 value'].set_raw(-2)
        map['INTEGER32 value'].set_raw(0x01020304)
        map['BOOLEAN value'].set_raw(False)
        map['BOOLEAN value 2'].set_raw(True)

        # Check expected data
        self.assertEqual(map.data, b'\xfd\xff\xef\x04\x03\x02\x01\x02')

        # Read values from data
        self.assertEqual(map['INTEGER16 value'].get_raw(), -3)
        self.assertEqual(map['UNSIGNED8 value'].get_raw(), 0xf)
        self.assertEqual(map['INTEGER8 value'].get_raw(), -2)
        self.assertEqual(map['INTEGER32 value'].get_raw(), 0x01020304)
        self.assertEqual(map['BOOLEAN value'].get_raw(), False)
        self.assertEqual(map['BOOLEAN value 2'].get_raw(), True)

        self.assertEqual(node.tpdo[1]['INTEGER16 value'].get_raw(), -3)
        self.assertEqual(node.tpdo[1]['UNSIGNED8 value'].get_raw(), 0xf)
        self.assertEqual(node.tpdo[1]['INTEGER8 value'].get_raw(), -2)
        self.assertEqual(node.tpdo[1]['INTEGER32 value'].get_raw(), 0x01020304)
        self.assertEqual(node.tpdo['INTEGER32 value'].get_raw(), 0x01020304)
        self.assertEqual(node.tpdo[1]['BOOLEAN value'].get_raw(), False)
        self.assertEqual(node.tpdo[1]['BOOLEAN value 2'].get_raw(), True)

        # Test different types of access
        self.assertEqual(node.pdo[0x1600]['INTEGER16 value'].get_raw(), -3)
        self.assertEqual(node.pdo['INTEGER16 value'].get_raw(), -3)
        self.assertEqual(node.pdo.tx[1]['INTEGER16 value'].get_raw(), -3)
        self.assertEqual(node.pdo[0x2001].get_raw(), -3)
        self.assertEqual(node.tpdo[0x2001].get_raw(), -3)
        self.assertEqual(node.pdo[0x2002].get_raw(), 0xf)
        self.assertEqual(node.pdo['0x2002'].get_raw(), 0xf)
        self.assertEqual(node.tpdo[0x2002].get_raw(), 0xf)
        self.assertEqual(node.pdo[0x1600][0x2002].get_raw(), 0xf)


if __name__ == "__main__":
    unittest.main()
