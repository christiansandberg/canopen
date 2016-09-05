import struct
import collections
import logging


logger = logging.getLogger(__name__)


BOOLEAN = 1
INTEGER8 = 2
INTEGER16 = 3
INTEGER32 = 4
UNSIGNED8 = 5
UNSIGNED16 = 6
UNSIGNED32 = 7
REAL32 = 8
VIS_STR = 9
REAL64 = 17
INTEGER64 = 21
UNSIGNED64 = 27


def import_any(filename):
    if filename.endswith(".eds"):
        from . import eds
        return eds.import_eds(filename)
    elif filename.endswith(".epf"):
        from . import epf
        return epf.import_epf(filename)


class ObjectDictionary(collections.Mapping):

    def __init__(self):
        self.indexes = collections.OrderedDict()
        self.names = collections.OrderedDict()

    def __getitem__(self, index):
        """Get Object Dictionary index."""
        return self.names.get(index) or self.indexes[index]

    def __iter__(self):
        """Iterates over all Object Dictionary indexes."""
        return iter(self.names)

    def __len__(self):
        return len(self.names)

    def __contains__(self, index):
        return index in self.names or index in self.indexes

    def add_object(self, obj):
        obj.parent = self
        self.indexes[obj.index] = obj
        self.names[obj.name] = obj


class Record(collections.Mapping):

    def __init__(self, name, index):
        self.parent = None
        self.index = index
        self.name = name
        self.subindexes = collections.OrderedDict()
        self.names = collections.OrderedDict()

    def __getitem__(self, subindex):
        return self.names.get(subindex) or self.subindexes[subindex]

    def __len__(self):
        return len(self.names)

    def __iter__(self):
        return iter(self.names)

    def __contains__(self, subindex):
        return subindex in self.names or subindex in self.subindexes

    def __eq__(self, other):
        return self.index == other.index

    def add_member(self, variable):
        variable.parent = self
        self.subindexes[variable.subindex] = variable
        self.names[variable.name] = variable


class Array(collections.Sequence):

    def __init__(self, name, index):
        self.parent = None
        self.index = index
        self.name = name
        self.variable = None

    def __getitem__(self, subindex):
        if subindex == 0:
            var = Variable("Number of Entries", self.index, 0)
            var.data_type = UNSIGNED8
        elif 0 < subindex < 256:
            var = Variable("%s [%d]" % (self.name, subindex), self.index, subindex)
            for attr in ("data_type", "unit", "factor", "min", "max",
                         "access_type", "value_descriptions"):
                var.__dict__[attr] = self.variable.__dict__[attr]
        else:
            raise IndexError("Subindex must be 0 - 255")

        var.parent = self
        return var

    def __len__(self):
        return 255


class Variable(object):
    """Object Dictionary VAR."""

    STRUCT_TYPES = {
        BOOLEAN: struct.Struct("?"),
        INTEGER8: struct.Struct("b"),
        INTEGER16: struct.Struct("<h"),
        INTEGER32: struct.Struct("<l"),
        INTEGER64: struct.Struct("<q"),
        UNSIGNED8: struct.Struct("B"),
        UNSIGNED16: struct.Struct("<H"),
        UNSIGNED32: struct.Struct("<L"),
        UNSIGNED64: struct.Struct("<Q"),
        REAL32: struct.Struct("<f"),
        REAL64: struct.Struct("<d")
    }

    def __init__(self, name, index, subindex=0):
        self.parent = None
        self.index = index
        self.subindex = subindex
        self.name = name
        self.data_type = UNSIGNED32
        self.access_type = "rw"
        self.unit = ""
        self.factor = 1
        self.min = None
        self.max = None
        self.value_descriptions = {}
        self.bit_definitions = {}

    def __eq__(self, other):
        return (self.index == other.index and
                self.subindex == other.subindex)

    def __len__(self):
        if self.data_type in self.STRUCT_TYPES:
            return self.STRUCT_TYPES[self.data_type].size
        else:
            return 1

    def add_value_description(self, value, descr):
        self.value_descriptions[value] = descr

    def add_bit_definition(self, name, bits):
        self.bit_definitions[name] = bits

    def decode_raw(self, data):
        if self.data_type == VIS_STR:
            value = data.decode("ascii")
        else:
            try:
                value, = self.STRUCT_TYPES[self.data_type].unpack(data)
            except struct.error:
                raise ObjectDictionaryError("Mismatch between expected and actual data size")
        return value

    def encode_raw(self, value):
        if self.data_type == VIS_STR:
            return value.encode("ascii")
        else:
            value = int(value)
            if self.min is not None and value < self.min:
                logger.warning("Value %d is less than min value %d", value, self.min)
            if self.max is not None and value > self.max:
                logger.warning("Value %d is greater than max value %d", value, self.max)
            try:
                return self.STRUCT_TYPES[self.data_type].pack(value)
            except struct.error:
                raise ValueError("Value does not fit in specified type")

    def decode_phys(self, data):
        value = self.decode_raw(data)
        try:
            value *= self.factor
        except TypeError:
            pass
        return value

    def encode_phys(self, value):
        try:
            value /= self.factor
            value = int(round(value))
        except TypeError:
            pass
        return self.encode_raw(value)

    def decode_desc(self, data):
        value = self.decode_raw(data)
        if not self.value_descriptions:
            raise ObjectDictionaryError("No value descriptions exist")
        elif value not in self.value_descriptions:
            raise ObjectDictionaryError("No value description exists for %d" % value)
        else:
            return self.value_descriptions[value]

    def encode_desc(self, desc):
        if not self.value_descriptions:
            raise ObjectDictionaryError("No value descriptions exist")
        else:
            for value, description in self.value_descriptions.items():
                if description == desc:
                    return self.encode_raw(value)
        valid_values = ", ".join(self.value_descriptions.values())
        error_text = "No value corresponds to '%s'. Valid values are: %s"
        raise ValueError(error_text % (desc, valid_values))

    def decode_bits(self, data, bits):
        if bits in self.bit_definitions:
            bits = self.bit_definitions[bits]
        value = self.decode_raw(data)
        mask = 0
        for bit in bits:
            mask |= 1 << bit
        return (value & mask) >> min(bits)

    def encode_bits(self, data, bits, value):
        if bits in self.bit_definitions:
            bits = self.bit_definitions[bits]
        temp = self.decode_raw(data)
        mask = 0
        for bit in bits:
            mask |= 1 << bit
        temp &= ~mask
        temp |= value << min(bits)
        return self.encode_raw(temp)


"""
class Bits(Parameter):

    def __init__(self, bits, name):
        self.mask = 0
        for bit in bits:
            self.mask += 1 << bit
        self.lowest_bit = min(bits)
        super(Bits, self).__init__(None, name)

    def decode_raw(self, data):
        try:
            value, = self.STRUCT_TYPES[self.data_type].unpack(data)
        except struct.error:
            raise ObjectDictionaryError("Mismatch between expected and actual data size")
        value &= self.mask
        value >>= self.lowest_bit
        return value

    def encode_raw(self, value):
        value = int(value)

        if value > (self.mask >> self.lowest_bit):
            raise ValueError("Value is outside bitfield range")

        data = self.parent.raw
        data &= ~self.mask
        data |= value << self.lowest_bit
        try:
            return self.STRUCT_TYPES[self.data_type].pack(value)
        except struct.error:
            raise ObjectDictionaryError("Value does not fit in specified type")
"""

class ObjectDictionaryError(Exception):
    pass
