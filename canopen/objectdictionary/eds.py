import re
try:
    from configparser import ConfigParser
except ImportError:
    from ConfigParser import RawConfigParser as ConfigParser
from canopen import objectdictionary


def import_eds(filename):
    od = objectdictionary.ObjectDictionary()
    eds = ConfigParser()
    eds.read(filename)

    for section in eds.sections():
        # Match groups
        match = re.match(r"^[0-9A-F]{4}$", section)
        if match is not None:
            index = int(section, 16)
            name = eds.get(section, "ParameterName")
            object_type = int(eds.get(section, "ObjectType"), 0)

            group = objectdictionary.Group(index, name)
            od.add_group(group)

            # If the group only contains one parameter
            if object_type == 7:
                par = build_parameter(eds, section, 0)
                group.add_parameter(par)
            elif object_type == 8 and eds.has_option(section, "CompactSubObj"):
                group.is_array = True
                last_subindex = objectdictionary.Parameter(0, "LastSubIndex")
                last_subindex.data_type = objectdictionary.UNSIGNED8
                par = build_parameter(eds, section, 1)
                group.add_parameter(last_subindex)
                group.add_parameter(par)

            continue

        # Match parameters
        match = re.match(r"^([0-9A-F]{4})sub([0-9A-F]+)$", section)
        if match is not None:
            index = int(match.group(1), 16)
            subindex = int(match.group(2), 16)
            par = build_parameter(eds, section, subindex)
            od[index].add_parameter(par)

    return od


def build_parameter(eds, section, subindex):
    name = eds.get(section, "ParameterName")
    par = objectdictionary.Parameter(subindex, name)
    par.data_type = int(eds.get(section, "DataType"), 0)
    if eds.has_option(section, "LowLimit"):
        par.min = eds.getint(section, "LowLimit")
    if eds.has_option(section, "HighLimit"):
        par.max = eds.getint(section, "HighLimit")
    return par
