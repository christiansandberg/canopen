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
                arr.variable = build_variable(eds, section, index, 1)
                od.add_object(arr)
            elif object_type == ARR:
                arr = objectdictionary.Array(name, index)
                arr.variable = build_variable(eds, section + "sub1", index, 1)
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
            var = build_variable(eds, section, index, subindex)
            od[index].add_member(var)

    return od


def build_variable(eds, section, index, subindex=0):
    name = eds.get(section, "ParameterName")
    var = objectdictionary.Variable(name, index, subindex)
    var.data_type = int(eds.get(section, "DataType"), 0)
    if eds.has_option(section, "LowLimit"):
        var.min = eds.getint(section, "LowLimit")
    if eds.has_option(section, "HighLimit"):
        var.max = eds.getint(section, "HighLimit")
    return var
