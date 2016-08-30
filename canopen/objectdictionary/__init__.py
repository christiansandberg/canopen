import struct
import collections


INTEGER8 = 2
INTEGER16 = 3
INTEGER32 = 4
UNSIGNED8 = 5
UNSIGNED16 = 6
UNSIGNED32 = 7
REAL32 = 8
VIS_STR = 9


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

    def add_group(self, group):
        group.parent = self
        self.indexes[group.index] = group
        self.names[group.name] = group


class Group(collections.Mapping):

    def __init__(self, index, name):
        self.parent = None
        self.index = index
        self.name = name
        self.is_array = False
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

    def add_parameter(self, par):
        par.parent = self
        self.subindexes[par.subindex] = par
        self.names[par.name] = par


class Parameter(object):
    """Object Dictionary subindex.
    """

    STRUCT_TYPES = {
        INTEGER8: struct.Struct("<b"),
        INTEGER16: struct.Struct("<h"),
        INTEGER32: struct.Struct("<l"),
        UNSIGNED8: struct.Struct("<B"),
        UNSIGNED16: struct.Struct("<H"),
        UNSIGNED32: struct.Struct("<L"),
        REAL32: struct.Struct("<f")
    }

    def __init__(self, subindex, name):
        self.parent = None
        self.subindex = subindex
        self.name = name
        self.data_type = UNSIGNED32
        self.unit = ""
        self.factor = 1
        self.min = None
        self.max = None
        self.value_descriptions = {}

    def __eq__(self, other):
        return (self.parent.index == other.parent.index and
                self.subindex == other.subindex)

    def __len__(self):
        if self.data_type in self.STRUCT_TYPES:
            return self.STRUCT_TYPES[self.data_type].size
        else:
            return 1

    def add_value_description(self, value, descr):
        self.value_descriptions[value] = descr

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
            try:
                return self.STRUCT_TYPES[self.data_type].pack(value)
            except struct.error:
                raise ObjectDictionaryError("Value does not fit in specified type")

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
        raise ObjectDictionaryError(error_text % (desc, valid_values))


class ObjectDictionaryError(Exception):
    pass
