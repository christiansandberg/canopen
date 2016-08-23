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

    def __init__(self, subindex, name):
        self.parent = None
        self.subindex = subindex
        self.name = name
        self.data_type = UNSIGNED32
        self.unit = ""
        self.factor = 1
        self.offset = 0
        self.min = None
        self.max = None
        self.value_descriptions = {}

    def __eq__(self, other):
        return (self.parent.index == other.parent.index and
                self.subindex == other.subindex)

    def add_value_description(self, value, descr):
        self.value_descriptions[value] = descr
