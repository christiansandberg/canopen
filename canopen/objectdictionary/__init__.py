"""
Object Dictionary module
"""
import struct
try:
    from collections.abc import MutableMapping, Mapping
except ImportError:
    from collections import MutableMapping, Mapping
import logging

from .datatypes import *

logger = logging.getLogger(__name__)


def import_od(source, node_id=None):
    """Parse an EDS, DCF, or EPF file.

    :param source:
        Path to object dictionary file or a file like object or an EPF XML tree.

    :return:
        An Object Dictionary instance.
    :rtype: canopen.ObjectDictionary
    """
    if source is None:
        return ObjectDictionary()
    if hasattr(source, "read"):
        # File like object
        filename = source.name
    elif hasattr(source, "tag"):
        # XML tree, probably from an EPF file
        filename = "od.epf"
    else:
        # Path to file
        filename = source
    suffix = filename[filename.rfind("."):].lower()
    if suffix in (".eds", ".dcf"):
        from . import eds
        return eds.import_eds(source, node_id)
    elif suffix == ".epf":
        from . import epf
        return epf.import_epf(source)
    else:
        raise NotImplementedError("No support for this format")


class ObjectDictionary(MutableMapping):
    """Representation of the object dictionary as a Python dictionary."""

    def __init__(self):
        self.indices = {}
        self.names = {}
        #: Default bitrate if specified by file
        self.bitrate = None
        #: Node ID if specified by file
        self.node_id = None

    def __getitem__(self, index):
        """Get object from object dictionary by name or index."""
        item = self.names.get(index) or self.indices.get(index)
        if item is None:
            name = "0x%X" % index if isinstance(index, int) else index
            raise KeyError("%s was not found in Object Dictionary" % name)
        return item

    def __setitem__(self, index, obj):
        assert index == obj.index or index == obj.name
        self.add_object(obj)

    def __delitem__(self, index):
        obj = self[index]
        del self.indices[obj.index]
        del self.names[obj.name]

    def __iter__(self):
        return iter(sorted(self.indices))

    def __len__(self):
        return len(self.indices)

    def __contains__(self, index):
        return index in self.names or index in self.indices

    def add_object(self, obj):
        """Add object to the object dictionary.

        :param obj:
            Should be either one of
            :class:`~canopen.objectdictionary.Variable`,
            :class:`~canopen.objectdictionary.Record`, or
            :class:`~canopen.objectdictionary.Array`.
        """
        obj.parent = self
        self.indices[obj.index] = obj
        self.names[obj.name] = obj

    def get_variable(self, index, subindex=0):
        """Get the variable object at specified index (and subindex if applicable).

        :return: Variable if found, else `None`
        :rtype: canopen.objectdictionary.Variable
        """
        obj = self.get(index)
        if isinstance(obj, Variable):
            return obj
        elif isinstance(obj, (Record, Array)):
            return obj.get(subindex)


class Record(MutableMapping):
    """Groups multiple :class:`~canopen.objectdictionary.Variable` objects using
    subindices.
    """

    #: Description for the whole record
    description = ""

    def __init__(self, name, index):
        #: The :class:`~canopen.ObjectDictionary` owning the record.
        self.parent = None
        #: 16-bit address of the record
        self.index = index
        #: Name of record
        self.name = name
        #: Storage location of index
        self.storage_location = None
        self.subindices = {}
        self.names = {}

    def __getitem__(self, subindex):
        item = self.names.get(subindex) or self.subindices.get(subindex)
        if item is None:
            raise KeyError("Subindex %s was not found" % subindex)
        return item

    def __setitem__(self, subindex, var):
        assert subindex == var.subindex
        self.add_member(var)

    def __delitem__(self, subindex):
        var = self[subindex]
        del self.subindices[var.subindex]
        del self.names[var.name]

    def __len__(self):
        return len(self.subindices)

    def __iter__(self):
        return iter(sorted(self.subindices))

    def __contains__(self, subindex):
        return subindex in self.names or subindex in self.subindices

    def __eq__(self, other):
        return self.index == other.index

    def add_member(self, variable):
        """Adds a :class:`~canopen.objectdictionary.Variable` to the record."""
        variable.parent = self
        self.subindices[variable.subindex] = variable
        self.names[variable.name] = variable


class Array(Mapping):
    """An array of :class:`~canopen.objectdictionary.Variable` objects using
    subindices.

    Actual length of array must be read from the node using SDO.
    """

    #: Description for the whole array
    description = ""

    def __init__(self, name, index):
        #: The :class:`~canopen.ObjectDictionary` owning the record.
        self.parent = None
        #: 16-bit address of the array
        self.index = index
        #: Name of array
        self.name = name
        #: Storage location of index
        self.storage_location = None
        self.subindices = {}
        self.names = {}

    def __getitem__(self, subindex):
        var = self.names.get(subindex) or self.subindices.get(subindex)
        if var is not None:
            # This subindex is defined
            pass
        elif isinstance(subindex, int) and 0 < subindex < 256:
            # Create a new variable based on first array item
            template = self.subindices[1]
            name = "%s_%x" % (template.name, subindex)
            var = Variable(name, self.index, subindex)
            var.parent = self
            for attr in ("data_type", "unit", "factor", "min", "max", "default",
                         "access_type", "description", "value_descriptions",
                         "bit_definitions", "storage_location"):
                if attr in template.__dict__:
                    var.__dict__[attr] = template.__dict__[attr]
        else:
            raise KeyError("Could not find subindex %r" % subindex)
        return var

    def __len__(self):
        return len(self.subindices)

    def __iter__(self):
        return iter(sorted(self.subindices))

    def __eq__(self, other):
        return self.index == other.index

    def add_member(self, variable):
        """Adds a :class:`~canopen.objectdictionary.Variable` to the record."""
        variable.parent = self
        self.subindices[variable.subindex] = variable
        self.names[variable.name] = variable


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
        #: The :class:`~canopen.ObjectDictionary`,
        #: :class:`~canopen.objectdictionary.Record` or
        #: :class:`~canopen.objectdictionary.Array` owning the variable
        self.parent = None
        #: 16-bit address of the object in the dictionary
        self.index = index
        #: 8-bit sub-index of the object in the dictionary
        self.subindex = subindex
        #: String representation of the variable
        self.name = name
        #: Physical unit
        self.unit = ""
        #: Factor between physical unit and integer value
        self.factor = 1
        #: Minimum allowed value
        self.min = None
        #: Maximum allowed value
        self.max = None
        #: Default value at start-up
        self.default = None
        #: The value of this variable stored in the object dictionary
        self.value = None
        #: Data type according to the standard as an :class:`int`
        self.data_type = None
        #: Access type, should be "rw", "ro", "wo", or "const"
        self.access_type = "rw"
        #: Description of variable
        self.description = ""
        #: Dictionary of value descriptions
        self.value_descriptions = {}
        #: Dictionary of bitfield definitions
        self.bit_definitions = {}
        #: Storage location of index
        self.storage_location = None

    def __eq__(self, other):
        return (self.index == other.index and
                self.subindex == other.subindex)

    def __len__(self):
        if self.data_type in self.STRUCT_TYPES:
            return self.STRUCT_TYPES[self.data_type].size * 8
        else:
            return 8

    @property
    def writable(self):
        return "w" in self.access_type

    @property
    def readable(self):
        return "r" in self.access_type or self.access_type == "const"

    def add_value_description(self, value, descr):
        """Associate a value with a string description.

        :param int value: Value to describe
        :param str desc: Description of value
        """
        self.value_descriptions[value] = descr

    def add_bit_definition(self, name, bits):
        """Associate bit(s) with a string description.

        :param str name: Name of bit(s)
        :param list bits: List of bits as integers
        """
        self.bit_definitions[name] = bits

    def decode_raw(self, data):
        if self.data_type == VISIBLE_STRING:
            return data.rstrip(b"\x00").decode("ascii", errors="ignore")
        elif self.data_type == UNICODE_STRING:
            # Is this correct?
            return data.rstrip(b"\x00").decode("utf_16_le", errors="ignore")
        elif self.data_type in self.STRUCT_TYPES:
            try:
                value, = self.STRUCT_TYPES[self.data_type].unpack(data)
                return value
            except struct.error:
                raise ObjectDictionaryError(
                    "Mismatch between expected and actual data size")
        else:
            # Just return the data as is
            return data

    def encode_raw(self, value):
        if isinstance(value, (bytes, bytearray)):
            return value
        elif self.data_type == VISIBLE_STRING:
            return value.encode("ascii")
        elif self.data_type == UNICODE_STRING:
            # Is this correct?
            return value.encode("utf_16_le")
        elif self.data_type in self.STRUCT_TYPES:
            if self.data_type in INTEGER_TYPES:
                value = int(value)
            if self.data_type in NUMBER_TYPES:
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
        elif self.data_type is None:
            raise ObjectDictionaryError("Data type has not been specified")
        else:
            raise TypeError(
                "Do not know how to encode %r to data type %Xh" % (
                    value, self.data_type))

    def decode_phys(self, value):
        if self.data_type in INTEGER_TYPES:
            value *= self.factor
        return value

    def encode_phys(self, value):
        if self.data_type in INTEGER_TYPES:
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
