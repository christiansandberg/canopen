import os.path
import unittest
import canopen

EDS_PATH = os.path.join(os.path.dirname(__file__), 'sample.eds')


class TestPDO(unittest.TestCase):

    def test_bit_mapping(self):
        node = canopen.Node(1, EDS_PATH)
        map = node.pdo.tx[1]
        map.add_variable('INTEGER16 value')
        map.add_variable('UNSIGNED8 value', length=4)
        map.add_variable('INTEGER8 value', length=4)
        map.add_variable('INTEGER32 value')

        # Write some values
        map['INTEGER16 value'].raw = -3
        map['UNSIGNED8 value'].raw = 0xf
        map['INTEGER8 value'].raw = -2
        map['INTEGER32 value'].raw = 0x01020304

        # Check expected data
        self.assertEqual(map.data, b'\xfd\xff\xef\x04\x03\x02\x01')

        # Read values from data
        self.assertEqual(map['INTEGER16 value'].raw, -3)
        self.assertEqual(map['UNSIGNED8 value'].raw, 0xf)
        self.assertEqual(map['INTEGER8 value'].raw, -2)
        self.assertEqual(map['INTEGER32 value'].raw, 0x01020304)

        
        self.assertEqual(node.tpdo[1]['INTEGER16 value'].raw, -3)
        self.assertEqual(node.tpdo[1]['UNSIGNED8 value'].raw, 0xf)
        self.assertEqual(node.tpdo[1]['INTEGER8 value'].raw, -2)
        self.assertEqual(node.tpdo[1]['INTEGER32 value'].raw, 0x01020304)
        self.assertEqual(node.tpdo['INTEGER32 value'].raw, 0x01020304)
        
        
        # Test diferent types of access
        self.assertEqual(node.pdo[0x1600]['INTEGER16 value'].raw, -3)
        self.assertEqual(node.pdo['INTEGER16 value'].raw, -3)
        self.assertEqual(node.pdo.tx[1]['INTEGER16 value'].raw, -3)
        


if __name__ == "__main__":
    unittest.main()
