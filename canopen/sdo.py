import collections
import struct
import logging
import threading


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


class SdoNode(collections.Mapping):

    def __init__(self, node_id):
        self.id = node_id
        self.parent = None
        self.response = None
        self.response_received = threading.Condition()

    def on_response(self, can_id, data):
        if can_id == 0x580 + self.id:
            with self.response_received:
                self.response = data
                self.response_received.notify_all()

    def send_request(self, sdo_request):
        retries = 5
        while retries:
            self.parent.network.send_message(0x600 + self.id, sdo_request)

            # Wait for node to respond
            with self.response_received:
                self.response = None
                self.response_received.wait(0.5)

            if self.response is None:
                retries -= 1
            else:
                retries = 0

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
            sdo_request[0] = REQUEST_SEGMENT_UPLOAD

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
            sdo_request[0] = REQUEST_SEGMENT_DOWNLOAD
            for pos in range(0, length, 7):
                sdo_request[1:8] = data[pos:pos+7]
                if pos+7 >= length:
                    sdo_request[0] |= 1
                response = self.send_request(sdo_request.ljust(8, b'\x00'))
                sdo_request[0] ^= 0x10
                # TODO: Check response

    def __getitem__(self, index):
        return Group(self, self.parent.object_dictionary[index])

    def __iter__(self):
        return iter(self.parent.object_dictionary)

    def __len__(self):
        return len(self.parent.object_dictionary)


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

    def __init__(self, node, od_par):
        self.node = node
        self.od = od_par
        self.index = od_par.parent.index
        self.subindex = od_par.subindex

    @property
    def data(self):
        return self.node.upload(self.index, self.subindex)

    @data.setter
    def data(self, data):
        self.node.download(self.index, self.subindex, data)

    @property
    def raw(self):
        value = self.od.decode_raw(self.data)
        text = "Value of %s.%s (0x%X:%d) in node %d = %d" % (
            self.od.parent.name, self.od.name, self.index,
            self.subindex, self.node.id, value)
        if value in self.od.value_descriptions:
            text += " (%s)" % self.od.value_descriptions[value]
        logger.debug(text)
        return value

    @raw.setter
    def raw(self, value):
        logger.debug("Writing %s.%s (0x%X:%d) = %s to node %d",
            self.od.parent.name, self.od.name, self.index,
            self.subindex, value, self.node.id)
        self.data = self.od.encode_raw(value)

    @property
    def phys(self):
        value = self.od.decode_phys(self.data)
        logger.debug("Value of %s.%s (0x%X:%d) in node %d = %s %s",
            self.od.parent.name, self.od.name, self.index,
            self.subindex, self.node.id, value, self.od.unit)
        return value

    @phys.setter
    def phys(self, value):
        logger.debug("Writing %s.%s (0x%X:%d) = %s to node %d",
            self.od.parent.name, self.od.name, self.index,
            self.subindex, value, self.node.id)
        self.data = self.od.encode_phys(value)

    @property
    def desc(self):
        value = self.od.decode_desc(self.data)
        logger.debug("Description of %s.%s (0x%X:%d) in node %d = %s",
            self.od.parent.name, self.od.name, self.index,
            self.subindex, self.node.id, value)
        return value

    @desc.setter
    def desc(self, desc):
        self.data = self.od.encode_desc(desc)


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
