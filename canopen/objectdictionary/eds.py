import re
try:
    from configparser import ConfigParser
except ImportError:
    from ConfigParser import RawConfigParser as ConfigParser
from canopen import objectdictionary


VAR = 7
ARR = 8
RECORD = 9


def import_eds(filename):
    od = objectdictionary.ObjectDictionary()
    eds = ConfigParser()
    eds.read(filename)

    for section in eds.sections():
        # Match indexes
        match = re.match(r"^[0-9A-F]{4}$", section)
        if match is not None:
            index = int(section, 16)
            name = eds.get(section, "ParameterName")
            object_type = int(eds.get(section, "ObjectType"), 0)

            if object_type == VAR:
                var = build_variable(eds, section, index)
                od.add_object(var)
            elif object_type == ARR and eds.has_option(section, "CompactSubObj"):
                arr = objectdictionary.Array(name, index)
                arr.template = build_variable(eds, section, index, 1)
                arr.length = int(eds.get(section, "CompactSubObj"), 0)
                od.add_object(arr)
            elif object_type == ARR:
                arr = objectdictionary.Array(name, index)
                arr.last_subindex = build_variable(
                    eds, section + "sub0", index, 0)
                arr.template = build_variable(eds, section + "sub1", index, 1)
                od.add_object(arr)
            elif object_type == RECORD:
                record = objectdictionary.Record(name, index)
                od.add_object(record)

            continue

        # Match subindexes
        match = re.match(r"^([0-9A-F]{4})sub([0-9A-F]+)$", section)
        if match is not None:
            index = int(match.group(1), 16)
            subindex = int(match.group(2), 16)
            entry = od[index]
            if isinstance(entry, objectdictionary.Record):
                var = build_variable(eds, section, index, subindex)
                entry.add_member(var)

    return od


def build_variable(eds, section, index, subindex=0):
    name = eds.get(section, "ParameterName")
    var = objectdictionary.Variable(name, index, subindex)
    var.data_type = int(eds.get(section, "DataType"), 0)
    var.access_type = eds.get(section, "AccessType").lower()
    if eds.has_option(section, "LowLimit"):
        try:
            var.min = int(eds.get(section, "LowLimit"), 0)
        except ValueError:
            pass
    if eds.has_option(section, "HighLimit"):
        try:
            var.max = int(eds.get(section, "HighLimit"), 0)
        except ValueError:
            pass
    return var
