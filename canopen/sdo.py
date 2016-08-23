import collections
import struct
import logging
import threading
from canopen import objectdictionary


logger = logging.getLogger(__name__)
# Command, index, subindex, value/abort code
SDO_STRUCT = struct.Struct("<BHB4s")


REQUEST_SEGMENT_DOWNLOAD = 0 << 5
REQUEST_DOWNLOAD = 1 << 5
REQUEST_UPLOAD = 2 << 5
REQUEST_SEGMENT_UPLOAD = 3 << 5

RESPONSE_SEGMENT_UPLOAD = 0 << 5
RESPONSE_SEGMENT_DOWNLOAD = 1 << 5
RESPONSE_UPLOAD = 2 << 5
RESPONSE_DOWNLOAD = 3 << 5

ABORTED = 0x80

EXPEDITED = 0x2
SIZE_SPECIFIED = 0x1


class Node(collections.Mapping):

    def __init__(self, node_id, object_dictionary):
        self.node_id = node_id
        self.object_dictionary = object_dictionary
        self.parent = None
        self.response = None
        self.response_received = threading.Condition()

    def on_response(self, can_id, data):
        with self.response_received:
            self.response = data
            self.response_received.notify_all()

    def send_request(self, sdo_request):
        attempts_left = 5
        while attempts_left:
            self.parent.network.send_message(0x600 + self.node_id, sdo_request)

            # Wait for node to respond
            with self.response_received:
                self.response = None
                self.response_received.wait(0.5)

            if self.response is not None:
                attempts_left = 0
            else:
                attempts_left -= 1

        if self.response is None:
            raise SdoCommunicationError("No SDO response received")
        elif self.response[0] == ABORTED:
            abort_code, = struct.unpack("<L", self.response[4:8])
            raise SdoAbortedError(abort_code)
        else:
            return self.response

    def upload(self, index, subindex):
        sdo_request = SDO_STRUCT.pack(REQUEST_UPLOAD, index, subindex, b'')
        response = self.send_request(sdo_request)
        res_command, res_index, res_subindex, res_data = SDO_STRUCT.unpack(response)

        # Check that the message is for us
        if res_index != index or res_subindex != subindex:
            raise SdoCommunicationError((
                "Node returned a value for 0x{:X}:{:d} instead, "
                "maybe there is another SDO master communicating "
                "on the same SDO channel?").format(index, subindex))

        ccs = res_command & 0xE0
        expedited = res_command & EXPEDITED
        size_specified = res_command & SIZE_SPECIFIED

        if ccs == RESPONSE_UPLOAD and expedited and size_specified:
            # Expedited upload
            length = 4 - ((res_command >> 2) & 0x3)
        elif ccs == RESPONSE_UPLOAD and size_specified:
            # Segmented upload
            length, = struct.unpack("<L", res_data)
            logger.debug("Starting segmented transfer for %d bytes", length)
            res_data = bytearray(length)
            sdo_request = bytearray(8)
            sdo_request[0] = 0x60

            for pos in range(0, length, 7):
                response = self.send_request(sdo_request)
                res_data[pos:pos+7] = response[1:8]
                sdo_request[0] ^= 0x10
        else:
            raise SdoCommunicationError("Unknown response type 0x%X" % res_command)

        return res_data[:length]

    def download(self, index, subindex, data):
        length = len(data)
        command = REQUEST_DOWNLOAD | SIZE_SPECIFIED

        if length <= 4:
            # Expedited download
            command |= EXPEDITED
            command |= (4 - length) << 2
            sdo_request = SDO_STRUCT.pack(command, index, subindex, data)
            response = self.send_request(sdo_request)
            # TODO: Check response
        else:
            # Segmented download
            req_data = struct.pack("<L", length)
            sdo_request = SDO_STRUCT.pack(command, index, subindex, req_data)
            response = self.send_request(sdo_request)
            # TODO: Check response

            sdo_request = bytearray(8)
            for pos in range(0, length, 7):
                sdo_request[1:8] = data[pos:pos+7]
                if pos+7 >= length:
                    sdo_request[0] |= 1
                self.send_request(sdo_request.ljust(8, b'\x00'))
                sdo_request[0] ^= 0x10
                # TODO: Check response

    def __getitem__(self, index):
        return Group(self, self.object_dictionary[index])

    def __iter__(self):
        return iter(self.object_dictionary)

    def __len__(self):
        return len(self.object_dictionary)


class Group(collections.Mapping):

    def __init__(self, node, od_group):
        self.node = node
        self.od = od_group

    def __getitem__(self, subindex):
        if self.od.is_array and isinstance(subindex, int) and subindex > 0:
            # Create a new parameter instance
            par = Parameter(self.node, self.od[1])
            # Set correct subindex
            par.subindex = subindex
            return par
        else:
            return Parameter(self.node, self.od[subindex])

    def __iter__(self):
        if self.od.is_array:
            # Return [1, 2, 3, ..., n] where n is the last subindex
            return iter(range(1, len(self) + 1))
        else:
            return iter(self.od)

    def __len__(self):
        return self[0].raw if self.od.is_array else len(self.od)

    def __contains__(self, subindex):
        if self.od.is_array and isinstance(subindex, int):
            return subindex <= len(self)
        else:
            return subindex in self.od


class Parameter(object):

    DATA_TYPES = {
        objectdictionary.INTEGER8: "b",
        objectdictionary.INTEGER16: "h",
        objectdictionary.INTEGER32: "l",
        objectdictionary.UNSIGNED8: "B",
        objectdictionary.UNSIGNED16: "H",
        objectdictionary.UNSIGNED32: "L",
        objectdictionary.REAL32: "f",
        objectdictionary.VIS_STR: "s"
    }

    def __init__(self, node, od_par):
        self.node = node
        self.od = od_par
        self.subindex = self.od.subindex
        self.struct = struct.Struct("<" + self.DATA_TYPES[od_par.data_type])

    @property
    def data(self):
        return self.node.upload(self.od.parent.index, self.subindex)

    @data.setter
    def data(self, data):
        self.node.download(self.od.parent.index, self.subindex, data)

    @property
    def raw(self):
        """Get raw value of parameter (SDO upload)"""
        logger.debug("Reading %s.%s (0x%X:%d) from node %d",
            self.od.parent.name, self.od.name, self.od.parent.index,
            self.subindex, self.node.node_id)

        data = self.data

        if self.od.data_type == objectdictionary.VIS_STR:
            value = data.decode("ascii")
        else:
            try:
                value, = self.struct.unpack(data)
            except struct.error:
                raise SdoError("Mismatch between expected and actual data size")

        logger.debug("Node returned %s", value)
        return value

    @raw.setter
    def raw(self, value):
        """Write raw value to parameter (SDO download)"""
        logger.debug("Writing %s.%s (0x%X:%d) = %s to node %d",
            self.od.parent.name, self.od.name, self.od.parent.index,
            self.subindex, value, self.node.node_id)

        if self.od.data_type == objectdictionary.VIS_STR:
            data = value.encode("ascii")
        else:
            data = self.struct.pack(int(value))

        self.data = data

    @property
    def phys(self):
        value = self.raw

        try:
            value *= self.od.factor
            value += self.od.offset
        except TypeError:
            pass

        return value

    @phys.setter
    def phys(self, value):
        try:
            value -= self.od.offset
            value /= self.od.factor
            value = int(round(value))
        except TypeError:
            pass

        self.raw = value

    @property
    def desc(self):
        value = self.raw

        if not self.od.value_descriptions:
            raise SdoError("No value descriptions exist")
        elif value not in self.od.value_descriptions:
            raise SdoError("No value description exists for %d" % value)
        else:
            return self.od.value_descriptions[value]

    @desc.setter
    def desc(self, desc):
        if not self.od.value_descriptions:
            raise SdoError("No value descriptions exist")
        else:
            for value, description in self.od.value_descriptions.items():
                if description == desc:
                    self.raw = value
                    return
        valid_values = ", ".join(self.od.value_descriptions.values())
        error_text = "No value corresponds to '%s'. Valid values are: %s"
        raise SdoError(error_text % (desc, valid_values))


class SdoError(Exception):
    pass


class SdoAbortedError(SdoError):
    """SDO abort exception."""

    CODES = {
        0x05040000: "Timeout of transfer communication detected",
        0x06010000: "Unsupported access to an object",
        0x06010001: "Attempt to read a write only object",
        0x06010002: "Attempt to write a read only object",
        0x06060000: "Access failed due to a hardware error",
        0x06090030: "Value range of parameter exceeded",
        0x08000021: ("Data can not be transferred or stored to the application "
                     "because of local control"),
        0x08000022: ("Data can not be transferred or stored to the application "
                     "because of the present device state")
    }

    def __init__(self, code):
        self.code = code

    def __str__(self):
        text = "Code 0x{:08X}".format(self.code)
        if self.code in self.CODES:
            text = text + ", " + self.CODES[self.code]
        return text


class SdoCommunicationError(SdoError):
    pass
