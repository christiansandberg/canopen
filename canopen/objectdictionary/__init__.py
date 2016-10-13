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

SIGNED_TYPES = (INTEGER8, INTEGER16, INTEGER32, INTEGER64)
UNSIGNED_TYPES = (BOOLEAN, UNSIGNED8, UNSIGNED16, UNSIGNED32, UNSIGNED64)
INTEGER_TYPES = SIGNED_TYPES + UNSIGNED_TYPES
FLOAT_TYPES = (REAL32, REAL64)
STRING_TYPES = (VIS_STR, )


def import_od(filename):
    """Parse an EDS or EPF file.

    :param str filename:
        Path to object dictionary file.

    :return:
        A :class:`canopen.ObjectDictionary` object.
    """
    if filename.endswith(".eds"):
        from . import eds
        return eds.import_eds(filename)
    elif filename.endswith(".epf"):
        from . import epf
        return epf.import_epf(filename)


class ObjectDictionary(collections.Mapping):
    """Representation of the object dictionary as a Python dictionary."""

    def __init__(self):
        self.indexes = collections.OrderedDict()
        self.names = collections.OrderedDict()
        #: Default bitrate if specified by file
        self.bitrate = None

    def __getitem__(self, index):
        """Get object from object dictionary by name or index."""
        return self.names.get(index) or self.indexes[index]

    def __iter__(self):
        return iter(self.names)

    def __len__(self):
        return len(self.names)

    def __contains__(self, index):
        return index in self.names or index in self.indexes

    def add_object(self, obj):
        """Add object to the object dictionary.

        :param obj:
            Should be either one of
            :class:`canopen.objectdictionary.Variable`,
            :class:`canopen.objectdictionary.Record`, or
            :class:`canopen.objectdictionary.Array`.
        """
        obj.parent = self
        self.indexes[obj.index] = obj
        self.names[obj.name] = obj


class Record(collections.Mapping):
    """Groups multiple :class:`canopen.objectdictionary.Variable` objects using
    subindexes.
    """

    def __init__(self, name, index):
        #: The :class:`canopen.ObjectDictionary` owning the record.
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
        """Adds a :class:`canopen.objectdictionary.Variable` to the record."""
        variable.parent = self
        self.subindexes[variable.subindex] = variable
        self.names[variable.name] = variable


class Array(collections.Sequence):
    """An array of :class:`canopen.objectdictionary.Variable` objects using
    subindexes.

    Actual length of array must be read from the node using SDO.
    """

    def __init__(self, name, index):
        #: The :class:`canopen.ObjectDictionary` owning the array.
        self.parent = None
        self.index = index
        self.name = name
        self.length = 255
        #: Variable to read to get length of array
        self.last_subindex = Variable(
            "Number of entries", index, 0)
        self.last_subindex.data_type = UNSIGNED8
        self.last_subindex.parent = self
        #: Each variable will be based on this with unique subindexes
        self.template = None

    def __getitem__(self, subindex):
        if subindex == 0 or subindex == self.last_subindex.name:
            return self.last_subindex
        elif isinstance(subindex, int) and 0 < subindex < 256:
            var = Variable(
                "%s [%d]" % (self.name, subindex), self.index, subindex)
            var.parent = self
            for attr in ("data_type", "unit", "factor", "min", "max",
                         "access_type", "value_descriptions"):
                var.__dict__[attr] = self.template.__dict__[attr]
            return var
        else:
            raise IndexError("Subindex must be 0 - 255")

    def __len__(self):
        return self.length


class Variable(object):
    """Simple variable."""

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
        #: The :class:`canopen.ObjectDictionary`,
        #: :class:`canopen.objectdictionary.Record` or
        #: :class:`canopen.objectdictionary.Array` owning the variable
        self.parent = None
        #: 16-bit address of the object in the dictionary
        self.index = index
        #: 8-bit sub-index of the object in the dictionary
        self.subindex = subindex
        #: String representation of the variable
        self.name = name
        #: Data type according to the standard as an :class:`int`
        self.data_type = UNSIGNED32
        #: Access type, should be "rw", "ro", "wo", or "const"
        self.access_type = "rw"
        #: Physical unit
        self.unit = ""
        #: Factor between physical unit and integer value
        self.factor = 1
        #: Minimum allowed value
        self.min = None
        #: Maximum allowed value
        self.max = None
        #: Dictionary of value descriptions
        self.value_descriptions = {}
        self.bit_definitions = {}

    def __eq__(self, other):
        return (self.index == other.index and
                self.subindex == other.subindex)

    def __len__(self):
        if self.data_type in self.STRUCT_TYPES:
            return self.STRUCT_TYPES[self.data_type].size * 8
        else:
            return 8

    def is_string(self):
        return self.data_type in STRING_TYPES

    def add_value_description(self, value, descr):
        self.value_descriptions[value] = descr

    def add_bit_definition(self, name, bits):
        self.bit_definitions[name] = bits

    def decode_raw(self, data):
        if self.is_string():
            value = data.decode("ascii")
        else:
            try:
                value, = self.STRUCT_TYPES[self.data_type].unpack(data)
            except struct.error:
                raise ObjectDictionaryError(
                    "Mismatch between expected and actual data size")
        return value

    def encode_raw(self, value):
        if self.is_string():
            return value.encode("ascii")
        else:
            if self.data_type in INTEGER_TYPES:
                value = int(value)
            if self.min is not None and value < self.min:
                logger.warning(
                    "Value %d is less than min value %d", value, self.min)
            if self.max is not None and value > self.max:
                logger.warning(
                    "Value %d is greater than max value %d",
                    value,
                    self.max)
            try:
                return self.STRUCT_TYPES[self.data_type].pack(value)
            except struct.error:
                raise ValueError("Value does not fit in specified type")

    def decode_phys(self, value):
        if not self.is_string():
            value *= self.factor
        return value

    def encode_phys(self, value):
        if not self.is_string():
            value /= self.factor
            value = int(round(value))
        return value

    def decode_desc(self, value):
        if not self.value_descriptions:
            raise ObjectDictionaryError("No value descriptions exist")
        elif value not in self.value_descriptions:
            raise ObjectDictionaryError(
                "No value description exists for %d" % value)
        else:
            return self.value_descriptions[value]

    def encode_desc(self, desc):
        if not self.value_descriptions:
            raise ObjectDictionaryError("No value descriptions exist")
        else:
            for value, description in self.value_descriptions.items():
                if description == desc:
                    return value
        valid_values = ", ".join(self.value_descriptions.values())
        error_text = "No value corresponds to '%s'. Valid values are: %s"
        raise ValueError(error_text % (desc, valid_values))

    def decode_bits(self, value, bits):
        try:
            bits = self.bit_definitions[bits]
        except (TypeError, KeyError):
            pass
        mask = 0
        for bit in bits:
            mask |= 1 << bit
        return (value & mask) >> min(bits)

    def encode_bits(self, original_value, bits, bit_value):
        try:
            bits = self.bit_definitions[bits]
        except (TypeError, KeyError):
            pass
        temp = original_value
        mask = 0
        for bit in bits:
            mask |= 1 << bit
        temp &= ~mask
        temp |= bit_value << min(bits)
        return temp


class ObjectDictionaryError(Exception):
    """Unsupported operation with the current Object Dictionary."""
    pass
