import re
import io
import logging
import copy
try:
    from configparser import RawConfigParser, NoOptionError, NoSectionError
except ImportError:
    from ConfigParser import RawConfigParser, NoOptionError, NoSectionError
from canopen import objectdictionary
from canopen.sdo import SdoClient

logger = logging.getLogger(__name__)

# Object type. Don't confuse with Data type
DOMAIN = 2
VAR = 7
ARR = 8
RECORD = 9

def import_eds(source, node_id):
    eds = RawConfigParser()
    eds.optionxform = str
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

    if eds.has_section("FileInfo"):
        od.__edsFileInfo = {
            opt: eds.get("FileInfo", opt)
            for opt in eds.options("FileInfo")
        }

    if eds.has_section("Comments"):
        linecount = eds.getint("Comments", "Lines")
        '\n'.join([
            eds.get("Comments","Line%i"%line)
            for line in range(1,linecount+1)
        ])

    if eds.has_section("DeviceInfo"):
        for rate in [10, 20, 50, 125, 250, 500, 800, 1000]:
            baudPossible = int(
                eds.get("DeviceInfo", "Baudrate_%i" % rate, fallback='0'), 0)
            if baudPossible != 0:
                od.device_information.allowed_baudrates.add(rate*1000)

        d = {"fallback": None}
        od.device_information.vendor_name = eds.get(
            "DeviceInfo", "VendorName", **d)
        od.device_information.vendor_number = eds.get(
            "DeviceInfo", "VendorNumber", **d)
        od.device_information.product_name = eds.get(
            "DeviceInfo", "ProductName", **d)
        od.device_information.product_number = eds.get(
            "DeviceInfo", "ProductNumber", **d)
        od.device_information.revision_number = eds.get(
            "DeviceInfo", "RevisionNumber", **d)
        od.device_information.order_code = eds.get(
            "DeviceInfo", "OrderCode", **d)
        od.device_information.simple_boot_up_master = eds.get(
            "DeviceInfo", "SimpleBootUpMaster", **d)
        od.device_information.simple_boot_up_slave = eds.get(
            "DeviceInfo", "simple_boot_up_slave", **d)
        od.device_information.granularity = eds.get(
            "DeviceInfo", "Granularity", **d)
        od.device_information.dynamic_channels_supported = eds.get(
            "DeviceInfo", "DynamicChannelsSupported", **d)
        od.device_information.group_messaging = eds.get(
            "DeviceInfo", "GroupMessaging", **d)
        od.device_information.nr_of_RXPDO = eds.get(
            "DeviceInfo", "NrOfRXPDO", **d)
        od.device_information.nr_of_TXPDO = eds.get(
            "DeviceInfo", "NrOfTXPDO", **d)
        od.device_information.LSS_supported = eds.get(
            "DeviceInfo", "LSS_Supported", **d)

    if eds.has_section("DeviceComissioning"):
        od.bitrate = int(eds.get("DeviceComissioning", "Baudrate")) * 1000
        od.node_id = int(eds.get("DeviceComissioning", "NodeID"), 0)

    for section in eds.sections():
        # Match dummy definitions
        match = re.match(r"^[Dd]ummy[Uu]sage$", section)
        if match is not None:
            for i in range(1, 8):
                key = "Dummy%04d" % i
                if eds.getint(section, key) == 1:
                    var = objectdictionary.Variable(key, i, 0)
                    var.data_type = i
                    var.access_type = "const"
                    od.add_object(var)

        # Match indexes
        match = re.match(r"^[0-9A-Fa-f]{4}$", section)
        if match is not None:
            index = int(section, 16)
            name = eds.get(section, "ParameterName")
            try:
                object_type = int(eds.get(section, "ObjectType"), 0)
            except NoOptionError:
                # DS306 4.6.3.2 object description
                # If the keyword ObjectType is missing, this is regarded as
                # "ObjectType=0x7" (=VAR).
                object_type = VAR
            try:
                storage_location = eds.get(section, "StorageLocation")
            except NoOptionError:
                storage_location = None

            if object_type in (VAR, DOMAIN):
                var = build_variable(eds, section, node_id, index)
                od.add_object(var)
            elif object_type == ARR and eds.has_option(section, "CompactSubObj"):
                arr = objectdictionary.Array(name, index)
                last_subindex = objectdictionary.Variable(
                    "Number of entries", index, 0)
                last_subindex.data_type = objectdictionary.UNSIGNED8
                arr.add_member(last_subindex)
                arr.add_member(build_variable(eds, section, node_id, index, 1))
                arr.storage_location = storage_location
                od.add_object(arr)
            elif object_type == ARR:
                arr = objectdictionary.Array(name, index)
                arr.storage_location = storage_location
                od.add_object(arr)
            elif object_type == RECORD:
                record = objectdictionary.Record(name, index)
                record.storage_location = storage_location
                od.add_object(record)

            continue

        # Match subindexes
        match = re.match(r"^([0-9A-Fa-f]{4})[S|s]ub([0-9A-Fa-f]+)$", section)
        if match is not None:
            index = int(match.group(1), 16)
            subindex = int(match.group(2), 16)
            entry = od[index]
            if isinstance(entry, (objectdictionary.Record,
                                  objectdictionary.Array)):
                var = build_variable(eds, section, node_id, index, subindex)
                entry.add_member(var)

        # Match [index]Name
        match = re.match(r"^([0-9A-Fa-f]{4})Name", section)
        if match is not None:
            index = int(match.group(1), 16)
            num_of_entries = int(eds.get(section, "NrOfEntries"))
            entry = od[index]
            # For CompactSubObj index 1 is were we find the variable
            src_var = od[index][1]
            for subindex in range(1, num_of_entries + 1):
                var = copy_variable(eds, section, subindex, src_var)
                if var is not None:
                    entry.add_member(var)

    return od


def import_from_node(node_id, network):
    """ Download the configuration from the remote node
    :param int node_id: Identifier of the node
    :param network: network object
    """
    # Create temporary SDO client
    sdo_client = SdoClient(0x600 + node_id, 0x580 + node_id, objectdictionary.ObjectDictionary())
    sdo_client.network = network
    # Subscribe to SDO responses
    network.subscribe(0x580 + node_id, sdo_client.on_response)
    # Create file like object for Store EDS variable
    try:
        eds_fp = sdo_client.open(0x1021, 0, "rt")
        od = import_eds(eds_fp, node_id)
    except Exception as e:
        logger.error("No object dictionary could be loaded for node %d: %s",
                     node_id, e)
        od = None
    finally:
        network.unsubscribe(0x580 + node_id)
    return od


def _convert_variable(node_id, var_type, value):
    if var_type in (objectdictionary.OCTET_STRING, objectdictionary.DOMAIN):
        return bytes.fromhex(value)
    elif var_type in (objectdictionary.VISIBLE_STRING, objectdictionary.UNICODE_STRING):
        return value
    elif var_type in objectdictionary.FLOAT_TYPES:
        return float(value)
    else:
        # COB-ID can contain '$NODEID+' so replace this with node_id before converting
        value = value.replace(" ","").upper()
        if '$NODEID' in value and node_id is not None:
            return int(re.sub(r'\+?\$NODEID\+?', '', value), 0) + node_id
        else:
            return int(value, 0)


def _revert_variable(var_type, value):
    if value is None:
        return None
    if var_type in (objectdictionary.OCTET_STRING, objectdictionary.DOMAIN):
        return bytes.hex(value)
    elif var_type in (objectdictionary.VISIBLE_STRING, objectdictionary.UNICODE_STRING):
        return value
    elif var_type in objectdictionary.FLOAT_TYPES:
        return value
    else:
        return "0x%02X" % value


def build_variable(eds, section, node_id, index, subindex=0):
    """Creates a object dictionary entry.
    :param eds: String stream of the eds file
    :param section:
    :param node_id: Node ID
    :param index: Index of the CANOpen object
    :param subindex: Subindex of the CANOpen object (if presente, else 0)
    """
    name = eds.get(section, "ParameterName")
    var = objectdictionary.Variable(name, index, subindex)
    try:
        var.storage_location = eds.get(section, "StorageLocation")
    except NoOptionError:
        var.storage_location = None
    var.data_type = int(eds.get(section, "DataType"), 0)
    var.access_type = eds.get(section, "AccessType").lower()
    if var.data_type > 0x1B:
        # The object dictionary editor from CANFestival creates an optional object if min max values are used
        # This optional object is then placed in the eds under the section [A0] (start point, iterates for more)
        # The eds.get function gives us 0x00A0 now convert to String without hex representation and upper case
        # The sub2 part is then the section where the type parameter stands
        try:
            var.data_type = int(eds.get("%Xsub1" % var.data_type, "DefaultValue"), 0)
        except NoSectionError:
            logger.warning("%s has an unknown or unsupported data type (%X)", name, var.data_type)
            # Assume DOMAIN to force application to interpret the byte data
            var.data_type = objectdictionary.DOMAIN

    var.pdo_mappable = bool(int(eds.get(section, "PDOMapping", fallback=0), 0))

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
            var.default_raw = eds.get(section, "DefaultValue")
            var.default = _convert_variable(node_id, var.data_type, eds.get(section, "DefaultValue"))
        except ValueError:
            pass
    if eds.has_option(section, "ParameterValue"):
        try:
            var.value_raw = eds.get(section, "ParameterValue")
            var.value = _convert_variable(node_id, var.data_type, eds.get(section, "ParameterValue"))
        except ValueError:
            pass
    return var

def copy_variable(eds, section, subindex, src_var):
    name = eds.get(section, str(subindex))
    var = copy.copy(src_var)
    # It is only the name and subindex that varies
    var.name = name
    var.subindex = subindex
    return var

def export_dcf(od, dest=None, fileInfo={}):
    return export_eds(od, dest, fileInfo, True)

def export_eds(od, dest=None, fileInfo={}, deviceComissioning=False):
    def export_object(obj, eds):
        if type(obj) is objectdictionary.Variable:
            return export_variable(obj, eds)
        if type(obj) is objectdictionary.Record:
            return export_record(obj, eds)
        if type(obj) is objectdictionary.Array:
            return export_array(obj, eds)

    def export_common(var, eds, section):
        eds.add_section(section)
        eds.set(section, "ParameterName", var.name)
        if var.storage_location:
            eds.set(section, "StorageLocation", var.storage_location)

    def export_variable(var, eds):
        if type(var.parent) is objectdictionary.ObjectDictionary:
            # top level variable
            section = "%04X" % var.index
        else:
            # nested variable
            section = "%04Xsub%X" % (var.index, var.subindex)

        export_common(var, eds, section)
        eds.set(section, "ObjectType", "0x%X" % VAR)
        if var.data_type:
            eds.set(section, "DataType", "0x%04X" % var.data_type)
        if var.access_type:
            eds.set(section, "AccessType", var.access_type)

        if getattr(var, 'default_raw', None) is not None:
            eds.set(section, "DefaultValue", var.default_raw)
        elif getattr(var, 'default', None) is not None:
            eds.set(section, "DefaultValue", _revert_variable(
                var.data_type, var.default))

        if deviceComissioning:
            if getattr(var, 'value_raw', None) is not None:
                eds.set(section, "ParameterValue", var.value_raw)
            elif getattr(var, 'value', None) is not None:
                eds.set(section, "ParameterValue",
                        _revert_variable(var.data_type, var.default))

        eds.set(section, "DataType", "0x%04X" % var.data_type)
        eds.set(section, "PDOMapping", hex(var.pdo_mappable))

        if getattr(var, 'min', None) is not None:
            eds.set(section, "LowLimit", var.min)
        if getattr(var, 'max', None) is not None:
            eds.set(section, "HighLimit", var.max)

    def export_record(var, eds):
        section = "%04X" % var.index
        export_common(var, eds, section)
        eds.set(section, "SubNumber", "0x%X" % len(var.subindices))
        ot = RECORD if type(var) is objectdictionary.Record else ARR
        eds.set(section, "ObjectType", "0x%X" % ot)
        for i in var:
            export_variable(var[i], eds)

    export_array = export_record

    eds = RawConfigParser()
    # both disables lowercasing, and allows int keys
    eds.optionxform = str

    from datetime import datetime as dt
    defmtime = dt.utcnow()

    try:
        # only if eds was loaded by us
        origFileInfo = od.__edsFileInfo
    except AttributeError:
        origFileInfo = {
            # just set some defaults
            "CreationDate": defmtime.strftime("%m-%d-%Y"),
            "CreationTime": defmtime.strftime("%I:%m%p"),
            "EdsVersion": 4.2,
        }

        fileInfo.setdefault("ModificationDate", defmtime.strftime("%m-%d-%Y"))
        fileInfo.setdefault("ModificationTime", defmtime.strftime("%I:%m%p"))
        for k, v in origFileInfo.items():
            fileInfo.setdefault(k, v)

    eds.add_section("FileInfo")
    for k, v in fileInfo.items():
        eds.set("FileInfo", k, v)

    eds.add_section("DeviceInfo")
    if od.device_information.vendor_name:
        eds.set(
            "DeviceInfo", "VendorName", od.device_information.vendor_name)
    if od.device_information.vendor_number:
        eds.set(
            "DeviceInfo", "VendorNumber", od.device_information.vendor_number)
    if od.device_information.product_name:
        eds.set(
            "DeviceInfo", "ProductName", od.device_information.product_name)
    if od.device_information.product_number:
        eds.set(
            "DeviceInfo", "ProductNumber", od.device_information.product_number)
    if od.device_information.revision_number:
        eds.set(
            "DeviceInfo", "RevisionNumber", od.device_information.revision_number)
    if od.device_information.order_code:
        eds.set(
            "DeviceInfo", "OrderCode", od.device_information.order_code)
    if od.device_information.simple_boot_up_master:
        eds.set(
            "DeviceInfo", "simple_boot_up_slave", od.device_information.simple_boot_up_master)
    if od.device_information.simple_boot_up_slave:
        eds.set(
            "DeviceInfo", "SimpleBootUpSlave", od.device_information.simple_boot_up_slave)
    if od.device_information.granularity:
        eds.set(
            "DeviceInfo", "Granularity", od.device_information.granularity)
    if od.device_information.dynamic_channels_supported:
        eds.set(
            "DeviceInfo", "DynamicChannelsSupported", od.device_information.dynamic_channels_supported)
    if od.device_information.group_messaging:
        eds.set(
            "DeviceInfo", "GroupMessaging", od.device_information.group_messaging)
    if od.device_information.nr_of_RXPDO:
        eds.set(
            "DeviceInfo", "NrOfRXPDO", od.device_information.nr_of_RXPDO)
    if od.device_information.nr_of_TXPDO:
        eds.set(
            "DeviceInfo", "NrOfTXPDO", od.device_information.nr_of_TXPDO)
    if od.device_information.LSS_supported:
        eds.set(
            "DeviceInfo", "LSS_Supported", od.device_information.LSS_supported)

    for rate in od.device_information.allowed_baudrates.union({10e3, 20e3, 50e3, 125e3, 250e3, 500e3, 800e3, 1000e3}):
        eds.set("DeviceInfo", "Baudrate_%i" % (rate/1000),
                int(rate in od.device_information.allowed_baudrates))

    if deviceComissioning and (od.bitrate or od.node_id):
        eds.add_section("DeviceComissioning")
        if od.bitrate:
            eds.set("DeviceComissioning", "Baudrate", int(od.bitrate / 1000))
        if od.node_id:
            eds.set("DeviceComissioning", "NodeID", int(od.node_id))

    eds.add_section("Comments")
    i=0
    for line in od.comments.splitlines():
        i += 1
        eds.set("Comments", "Line%i"%i, line)
    eds.set("Comments", "Lines", i)

    eds.add_section("DummyUsage")
    for i in range(1, 8):
        key = "Dummy%04d" % i
        eds.set("DummyUsage", key, 1 if (key in od) else 0)

    def mandatoryIndices(x):
        return x in {0x1000, 0x1001, 0x1018}

    def manufacturerIndices(x):
        return x in range(0x2000, 0x6000)

    def optionalIndices(x):
        return (x > 0x1001 and
        not mandatoryIndices(x) and
        not manufacturerIndices(x))

    supportedMantatoryIndices = list(filter(mandatoryIndices, od))
    supportedOptionalIndices = list(filter(optionalIndices, od))
    supportedManufacturerIndices = list(filter(manufacturerIndices, od))

    def add_list(section, list):
        eds.add_section(section)
        eds.set(section, "SupportedObjects", len(list))
        for i in range(0, len(list)):
            eds.set(section, (i + 1), "0x%04X" % list[i])
        for index in list:
            export_object(od[index], eds)

    add_list("MandatoryObjects", supportedMantatoryIndices)
    add_list("OptionalObjects", supportedOptionalIndices)
    add_list("ManufacturerObjects", supportedManufacturerIndices)

    if not dest:
        import sys
        dest = sys.stdout

    eds.write(dest, False)
