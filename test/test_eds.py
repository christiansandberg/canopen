import os
import unittest
import canopen
from canopen.objectdictionary.eds import _signed_int_from_hex

EDS_PATH = os.path.join(os.path.dirname(__file__), 'sample.eds')


class TestEDS(unittest.TestCase):

    test_data = {
        "int8": [
            {"hex_str": "7F", "bit_length": 8, "expected": 127},
            {"hex_str": "80", "bit_length": 8, "expected": -128},
            {"hex_str": "FF", "bit_length": 8, "expected": -1},
            {"hex_str": "00", "bit_length": 8, "expected": 0},
            {"hex_str": "01", "bit_length": 8, "expected": 1}
        ],
        "int16": [
            {"hex_str": "7FFF", "bit_length": 16, "expected": 32767},
            {"hex_str": "8000", "bit_length": 16, "expected": -32768},
            {"hex_str": "FFFF", "bit_length": 16, "expected": -1},
            {"hex_str": "0000", "bit_length": 16, "expected": 0},
            {"hex_str": "0001", "bit_length": 16, "expected": 1}
        ],
        "int32": [
            {"hex_str": "7FFFFFFF", "bit_length": 32, "expected": 2147483647},
            {"hex_str": "80000000", "bit_length": 32, "expected": -2147483648},
            {"hex_str": "FFFFFFFF", "bit_length": 32, "expected": -1},
            {"hex_str": "00000000", "bit_length": 32, "expected": 0},
            {"hex_str": "00000001", "bit_length": 32, "expected": 1}
        ],
        "int64": [
            {"hex_str": "7FFFFFFFFFFFFFFF", "bit_length": 64, "expected": 9223372036854775807},
            {"hex_str": "8000000000000000", "bit_length": 64, "expected": -9223372036854775808},
            {"hex_str": "FFFFFFFFFFFFFFFF", "bit_length": 64, "expected": -1},
            {"hex_str": "0000000000000000", "bit_length": 64, "expected": 0},
            {"hex_str": "0000000000000001", "bit_length": 64, "expected": 1}
        ]
    }

    def setUp(self):
        self.od = canopen.import_od(EDS_PATH, 2)

    def test_load_nonexisting_file(self):
        with self.assertRaises(IOError):
            canopen.import_od('/path/to/wrong_file.eds')

    def test_load_file_object(self):
        with open(EDS_PATH) as fp:
            od = canopen.import_od(fp)
        self.assertTrue(len(od) > 0)

    def test_variable(self):
        var = self.od['Producer heartbeat time']
        self.assertIsInstance(var, canopen.objectdictionary.ODVariable)
        self.assertEqual(var.index, 0x1017)
        self.assertEqual(var.subindex, 0)
        self.assertEqual(var.name, 'Producer heartbeat time')
        self.assertEqual(var.data_type, canopen.objectdictionary.UNSIGNED16)
        self.assertEqual(var.access_type, 'rw')
        self.assertEqual(var.default, 0)
        self.assertFalse(var.relative)

    def test_relative_variable(self):
        var = self.od['Receive PDO 0 Communication Parameter']['COB-ID use by RPDO 1']
        self.assertTrue(var.relative)
        self.assertEqual(var.default, 512 + self.od.node_id)

    def test_record(self):
        record = self.od['Identity object']
        self.assertIsInstance(record, canopen.objectdictionary.ODRecord)
        self.assertEqual(len(record), 5)
        self.assertEqual(record.index, 0x1018)
        self.assertEqual(record.name, 'Identity object')
        var = record['Vendor-ID']
        self.assertIsInstance(var, canopen.objectdictionary.ODVariable)
        self.assertEqual(var.name, 'Vendor-ID')
        self.assertEqual(var.index, 0x1018)
        self.assertEqual(var.subindex, 1)
        self.assertEqual(var.data_type, canopen.objectdictionary.UNSIGNED32)
        self.assertEqual(var.access_type, 'ro')

    def test_record_with_limits(self):
        int8 = self.od[0x3020]
        self.assertEqual(int8.min, 0)
        self.assertEqual(int8.max, 127)
        uint8 = self.od[0x3021]
        self.assertEqual(uint8.min, 2)
        self.assertEqual(uint8.max, 10)
        int32 = self.od[0x3030]
        self.assertEqual(int32.min, -2147483648)
        self.assertEqual(int32.max, -1)
        int64 = self.od[0x3040]
        self.assertEqual(int64.min, -10)
        self.assertEqual(int64.max, +10)

    def test_signed_int_from_hex(self):
        for data_type, test_cases in self.test_data.items():
            for test_case in test_cases:
                with self.subTest(data_type=data_type, test_case=test_case):
                    result = _signed_int_from_hex('0x' + test_case["hex_str"], test_case["bit_length"])
                    self.assertEqual(result, test_case["expected"])

    def test_array_compact_subobj(self):
        array = self.od[0x1003]
        self.assertIsInstance(array, canopen.objectdictionary.ODArray)
        self.assertEqual(array.index, 0x1003)
        self.assertEqual(array.name, 'Pre-defined error field')
        var = array[5]
        self.assertIsInstance(var, canopen.objectdictionary.ODVariable)
        self.assertEqual(var.name, 'Pre-defined error field_5')
        self.assertEqual(var.index, 0x1003)
        self.assertEqual(var.subindex, 5)
        self.assertEqual(var.data_type, canopen.objectdictionary.UNSIGNED32)
        self.assertEqual(var.access_type, 'ro')

    def test_explicit_name_subobj(self):
        name = self.od[0x3004].name
        self.assertEqual(name, 'Sensor Status')
        name = self.od[0x3004][1].name
        self.assertEqual(name, 'Sensor Status 1')
        name = self.od[0x3004][3].name
        self.assertEqual(name, 'Sensor Status 3')
        value = self.od[0x3004][3].default
        self.assertEqual(value, 3)

    def test_parameter_name_with_percent(self):
        name = self.od[0x3003].name
        self.assertEqual(name, 'Valve % open')

    def test_compact_subobj_parameter_name_with_percent(self):
        name = self.od[0x3006].name
        self.assertEqual(name, 'Valve 1 % Open')

    def test_sub_index_w_capital_s(self):
        name = self.od[0x3010][0].name
        self.assertEqual(name, 'Temperature')

    def test_dummy_variable(self):
        var = self.od['Dummy0003']
        self.assertIsInstance(var, canopen.objectdictionary.ODVariable)
        self.assertEqual(var.index, 0x0003)
        self.assertEqual(var.subindex, 0)
        self.assertEqual(var.name, 'Dummy0003')
        self.assertEqual(var.data_type, canopen.objectdictionary.INTEGER16)
        self.assertEqual(var.access_type, 'const')
        self.assertEqual(len(var), 16)

    def test_dummy_variable_undefined(self):
        with self.assertRaises(KeyError):
            var_undef = self.od['Dummy0001']
    
    def test_reading_factor(self):
        var = self.od['EDS file extensions']['FactorAndDescription']
        self.assertEqual(var.factor, 0.1)
        self.assertEqual(var.description, "This is the a test description")
        self.assertEqual(var.unit,'mV')
        var2 = self.od['EDS file extensions']['Error Factor and No Description']
        self.assertEqual(var2.description, '')
        self.assertEqual(var2.factor, 1)
        self.assertEqual(var2.unit, '')
        


    def test_comments(self):
        self.assertEqual(self.od.comments,
                         """
|-------------|
| Don't panic |
|-------------|
""".strip())

    def test_export_eds(self):
        import tempfile
        from pathlib import Path
        with tempfile.TemporaryDirectory() as tempdir:
            for doctype in {"eds", "dcf"}:
                tempfile = str(Path(tempdir, "test." + doctype))
                with open(tempfile, "w+") as tempeds:
                    print("exporting %s to " % doctype + tempeds.name)
                    canopen.export_od(self.od, tempeds, doc_type=doctype)

                exported_od = canopen.import_od(tempfile)

                for index in exported_od:
                    self.assertIn(exported_od[index].name, self.od)
                    self.assertIn(index, self.od)

                for index in self.od:
                    if index < 0x0008:
                        # ignore dummies
                        continue
                    self.assertIn(self.od[index].name, exported_od)
                    self.assertIn(index, exported_od)

                    actual_object = exported_od[index]
                    expected_object = self.od[index]
                    self.assertEqual(type(actual_object), type(expected_object))
                    self.assertEqual(actual_object.name, expected_object.name)

                    if isinstance(actual_object, canopen.objectdictionary.ODVariable):
                        expected_vars = [expected_object]
                        actual_vars = [actual_object]
                    else:
                        expected_vars = [expected_object[idx] for idx in expected_object]
                        actual_vars = [actual_object[idx] for idx in actual_object]

                    for prop in [
                        "allowed_baudrates",
                        "vendor_name",
                        "vendor_number",
                        "product_name",
                        "product_number",
                        "revision_number",
                        "order_code",
                        "simple_boot_up_master",
                        "simple_boot_up_slave",
                        "granularity",
                        "dynamic_channels_supported",
                        "group_messaging",
                        "nr_of_RXPDO",
                        "nr_of_TXPDO",
                        "LSS_supported",
                    ]:
                        self.assertEqual(getattr(self.od.device_information, prop),
                                         getattr(exported_od.device_information, prop),
                                         f"prop {prop!r} mismatch on DeviceInfo")

                    for evar, avar in zip(expected_vars, actual_vars):
                        self.assertEqual(getattr(avar, "data_type", None), getattr(evar, "data_type", None),
                                         " mismatch on %04X:%X" % (evar.index, evar.subindex))
                        self.assertEqual(getattr(avar, "default_raw", None), getattr(evar, "default_raw", None),
                                         " mismatch on %04X:%X" % (evar.index, evar.subindex))
                        self.assertEqual(getattr(avar, "min", None), getattr(evar, "min", None),
                                         " mismatch on %04X:%X" % (evar.index, evar.subindex))
                        self.assertEqual(getattr(avar, "max", None), getattr(evar, "max", None),
                                         " mismatch on %04X:%X" % (evar.index, evar.subindex))
                        if doctype == "dcf":
                            self.assertEqual(getattr(avar, "value", None), getattr(evar, "value", None),
                                             " mismatch on %04X:%X" % (evar.index, evar.subindex))

                        self.assertEqual(self.od.comments, exported_od.comments)
