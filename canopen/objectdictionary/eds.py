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

    if eds.has_section("DeviceComissioning"):
        od.bitrate = int(eds.get("DeviceComissioning", "Baudrate")) * 1000
        od.node_id = int(eds.get("DeviceComissioning", "NodeID"))

    for section in eds.sections():
        # Match indexes
        match = re.match(r"^[0-9A-Fa-f]{4}$", section)
        if match is not None:
            index = int(section, 16)
            name = eds.get(section, "ParameterName")
            object_type = int(eds.get(section, "ObjectType"), 0)

            if object_type == VAR:
                var = build_variable(eds, section, index)
                od.add_object(var)
            elif object_type == ARR and eds.has_option(section, "CompactSubObj"):
                arr = objectdictionary.Array(name, index)
                last_subindex = objectdictionary.Variable(
                    "Number of entries", index, 0)
                last_subindex.data_type = objectdictionary.UNSIGNED8
                arr.add_member(last_subindex)
                arr.add_member(build_variable(eds, section, index, 1))
                od.add_object(arr)
            elif object_type == ARR:
                arr = objectdictionary.Array(name, index)
                od.add_object(arr)
            elif object_type == RECORD:
                record = objectdictionary.Record(name, index)
                od.add_object(record)

            continue

        # Match subindexes
        match = re.match(r"^([0-9A-Fa-f]{4})sub([0-9A-Fa-f]+)$", section)
        if match is not None:
            index = int(match.group(1), 16)
            subindex = int(match.group(2), 16)
            entry = od[index]
            if isinstance(entry, (objectdictionary.Record,
                                  objectdictionary.Array)):
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
