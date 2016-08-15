import collections


INTEGER8 = 1
INTEGER16 = 2
INTEGER32 = 3
UNSIGNED8 = 4
UNSIGNED16 = 5
UNSIGNED32 = 6
REAL32 = 7
VIS_STR = 8


def import_any(filename):
    if filename.endswith(".epf"):
        from . import epf
        return epf.import_epf(filename)


class ObjectDictionary(collections.Mapping):

    def __init__(self):
        self.indexes = collections.OrderedDict()
        self.names = collections.OrderedDict()

    def add_group(self, group):
        self.indexes[group.index] = group
        self.names[group.name] = group

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


class Group(collections.Mapping):

    def __init__(self, parent, index, name):
        self.parent = parent
        self.index = index
        self.name = name
        self.is_array = False
        self.subindexes = collections.OrderedDict()
        self.names = collections.OrderedDict()
    
    def add_parameter(self, par):
        self.subindexes[par.subindex] = par
        self.names[par.name] = par

    def __getitem__(self, subindex):
        if self.is_array and isinstance(subindex, int) and subindex > 0:
            # Create a new parameter instance
            par = self[1]
            # Set correct subindex
            par.subindex = subindex
            return par
        else:
            return self.names.get(subindex) or self.subindexes[subindex]

    def __len__(self):
        return len(self.names)

    def __iter__(self):
        return iter(self.names)

    def __contains__(self, subindex):
        return subindex in self.names or subindex in self.subindexes

    def __eq__(self, other):
        return self.index == other.index


class Parameter(object):
    """Object Dictionary subindex.
    """

    def __init__(self, parent, subindex, name):
        self.parent = parent
        self.subindex = subindex
        self.name = name
        self.data_type = UNSIGNED32
        self.unit = ''
        self.factor = 1
        self.offset = 0
        self.value_descriptions = {}

    def add_value_description(self, value, descr):
        self.value_descriptions[value] = descr

    def __eq__(self, other):
        return (self.parent.index == other.parent.index and
                self.subindex == other.subindex)
