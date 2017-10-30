import re
import io
import logging
try:
    from configparser import ConfigParser
except ImportError:
    from ConfigParser import RawConfigParser as ConfigParser
from canopen import objectdictionary
from canopen.sdo import SdoClient, ReadableStream


logger = logging.getLogger(__name__)


VAR = 7
ARR = 8
RECORD = 9


def import_eds(source, node_id):
    eds = ConfigParser()
    if hasattr(source, "read"):
        fp = source
    else:
        fp = open(source)
    try:
        # Python 3
        eds.read_file(fp)
    except AttributeError:
        # Python 2
        eds.readfp(fp)
    fp.close()
    od = objectdictionary.ObjectDictionary()
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


def import_from_node(node_id, network):
    # Create temporary SDO client
    sdo_client = SdoClient(node_id, None)
    sdo_client.network = network
    # Subscribe to SDO responses
    network.subscribe(0x580 + node_id, sdo_client.on_response)
    # Create file like object for Store EDS variable
    try:
        eds_fp = ReadableStream(sdo_client, 0x1021)
        eds_fp = io.BufferedReader(eds_fp)
        eds_fp = io.TextIOWrapper(eds_fp, "ascii")
        od = import_eds(eds_fp, node_id)
    except Exception as e:
        logger.error("No object dictionary could be loaded for node %d: %s",
                     node_id, e)
        od = None
    finally:
        network.unsubscribe(0x580 + node_id)
    return od


def build_variable(eds, section, index, subindex=0):
    name = eds.get(section, "ParameterName")
    var = objectdictionary.Variable(name, index, subindex)
    var.data_type = int(eds.get(section, "DataType"), 0)
    var.access_type = eds.get(section, "AccessType").lower()
    if var.data_type > 0x1B:
        # The object dictionary editor from CANFestival creates an optional object if min max values are used
        # This optional object is then placed in the eds under the section [A0] (start point, iterates for more)
        # The eds.get function gives us 0x00A0 now convert to String without hex representation and upper case
        # The sub2 part is then the section where the type parameter stands
        var.data_type = int(eds.get("%Xsub1" % var.data_type, "DataType"), 0)

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
    if eds.has_option(section, "DefaultValue"):
        try:
            var.default = int(eds.get(section, "DefaultValue"), 0)
        except ValueError:
            pass
    return var
