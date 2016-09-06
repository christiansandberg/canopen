import collections
import struct
import logging
import threading
from . import objectdictionary


logger = logging.getLogger(__name__)


# Command, index, subindex, data
SDO_STRUCT = struct.Struct("<BHB4s")


REQUEST_SEGMENT_DOWNLOAD = 0 << 5
REQUEST_DOWNLOAD = 1 << 5
REQUEST_UPLOAD = 2 << 5
REQUEST_SEGMENT_UPLOAD = 3 << 5

RESPONSE_SEGMENT_UPLOAD = 0 << 5
RESPONSE_SEGMENT_DOWNLOAD = 1 << 5
RESPONSE_UPLOAD = 2 << 5
RESPONSE_DOWNLOAD = 3 << 5
RESPONSE_ABORTED = 4 << 5

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
            # Wait for node to respond
            with self.response_received:
                self.parent.network.send_message(0x600 + self.id, sdo_request)
                self.response = None
                self.response_received.wait(2.0)

            if self.response is None:
                retries -= 1
            else:
                retries = 0

        if self.response is None:
            raise SdoCommunicationError("No SDO response received")
        elif self.response[0] == RESPONSE_ABORTED:
            abort_code, = struct.unpack("<L", self.response[4:8])
            raise SdoAbortedError(abort_code)
        else:
            return self.response

    def upload(self, index, subindex):
        request = SDO_STRUCT.pack(REQUEST_UPLOAD, index, subindex, b'')
        response = self.send_request(request)
        res_command, res_index, res_subindex, res_data = SDO_STRUCT.unpack(response)

        assert res_command & 0xE0 == RESPONSE_UPLOAD

        # Check that the message is for us
        if res_index != index or res_subindex != subindex:
            raise SdoCommunicationError((
                "Node returned a value for 0x{:X}:{:d} instead, "
                "maybe there is another SDO master communicating "
                "on the same SDO channel?").format(res_index, res_subindex))

        expedited = res_command & EXPEDITED
        size_specified = res_command & SIZE_SPECIFIED

        length = None

        if expedited and size_specified:
            # Expedited upload
            length = 4 - ((res_command >> 2) & 0x3)
        elif not expedited:
            # Segmented upload
            if size_specified:
                length, = struct.unpack("<L", res_data)

            request = bytearray(8)
            request[0] = REQUEST_SEGMENT_UPLOAD
            res_data = b''
            while True:
                response = self.send_request(request)
                assert response[0] & 0xE0 == RESPONSE_SEGMENT_UPLOAD
                res_data += response[1:8]
                request[0] ^= 0x10
                if response[0] & 1:
                    break

        return res_data[:length] if length is not None else res_data

    def download(self, index, subindex, data):
        length = len(data)
        command = REQUEST_DOWNLOAD | SIZE_SPECIFIED

        if length <= 4:
            # Expedited download
            command |= EXPEDITED
            command |= (4 - length) << 2
            request = SDO_STRUCT.pack(command, index, subindex, data)
            response = self.send_request(request)
            assert response[0] == RESPONSE_DOWNLOAD
        else:
            # Segmented download
            length_data = struct.pack("<L", length)
            request = SDO_STRUCT.pack(command, index, subindex, length_data)
            response = self.send_request(request)
            assert response[0] == RESPONSE_DOWNLOAD

            request = bytearray(8)
            request[0] = REQUEST_SEGMENT_DOWNLOAD
            for pos in range(0, length, 7):
                request[1:8] = data[pos:pos+7]
                if pos+7 >= length:
                    request[0] |= 1
                response = self.send_request(request.ljust(8, b'\x00'))
                request[0] ^= 0x10
                assert response[0] & 0xE0 == RESPONSE_SEGMENT_DOWNLOAD

    def __getitem__(self, index):
        entry = self.parent.object_dictionary[index]
        if isinstance(entry, objectdictionary.Variable):
            return Variable(self, entry)
        elif isinstance(entry, objectdictionary.Record):
            return Record(self, entry)
        elif isinstance(entry, objectdictionary.Array):
            return Array(self, entry)

    def __iter__(self):
        return iter(self.parent.object_dictionary)

    def __len__(self):
        return len(self.parent.object_dictionary)


class Record(collections.Mapping):

    def __init__(self, node, od):
        self.node = node
        self.od = od

    def __getitem__(self, subindex):
        return Variable(self.node, self.od[subindex])

    def __iter__(self):
        return iter(self.od)

    def __len__(self):
        return len(self.od)

    def __contains__(self, subindex):
        return subindex in self.od


class Array(collections.Mapping):

    def __init__(self, node, od):
        self.node = node
        self.od = od

    def __getitem__(self, subindex):
        return Variable(self.node, self.od[subindex])

    def __iter__(self):
        return iter(range(1, len(self) + 1))

    def __len__(self):
        return self[0].raw

    def __contains__(self, subindex):
        return 0 <= subindex <= len(self)


class Variable(object):

    def __init__(self, node, od):
        self.node = node
        self.od = od
        self.bits = Bits(self)

    @property
    def data(self):
        if self.od.access_type == "wo":
            logger.warning("Variable is write only")
        return self.node.upload(self.od.index, self.od.subindex)

    @data.setter
    def data(self, data):
        if "w" not in self.od.access_type:
            logger.warning("Variable is read only")
        self.node.download(self.od.index, self.od.subindex, data)

    @property
    def raw(self):
        value = self.od.decode_raw(self.data)
        text = "Value of %s (0x%X:%d) in node %d is %d" % (
            self.od.name, self.od.index,
            self.od.subindex, self.node.id, value)
        if value in self.od.value_descriptions:
            text += " (%s)" % self.od.value_descriptions[value]
        logger.debug(text)
        return value

    @raw.setter
    def raw(self, value):
        logger.debug("Writing %s (0x%X:%d) = %s to node %d",
            self.od.name, self.od.index,
            self.od.subindex, value, self.node.id)
        self.data = self.od.encode_raw(value)

    @property
    def phys(self):
        value = self.od.decode_phys(self.data)
        logger.debug("Value of %s (0x%X:%d) in node %d is %s %s",
            self.od.name, self.od.index,
            self.od.subindex, self.node.id, value, self.od.unit)
        return value

    @phys.setter
    def phys(self, value):
        logger.debug("Writing %s (0x%X:%d) = %s to node %d",
            self.od.name, self.od.index,
            self.od.subindex, value, self.node.id)
        self.data = self.od.encode_phys(value)

    @property
    def desc(self):
        value = self.od.decode_desc(self.data)
        logger.debug("Description of %s (0x%X:%d) in node %d is %s",
            self.od.name, self.od.index,
            self.od.subindex, self.node.id, value)
        return value

    @desc.setter
    def desc(self, desc):
        logger.debug("Setting description of %s (0x%X:%d) in node %d to %s",
            self.od.name, self.od.index,
            self.od.subindex, self.node.id, desc)
        self.data = self.od.encode_desc(desc)


class Bits(object):

    def __init__(self, variable):
        self.variable = variable

    def _get_bits(self, key):
        if isinstance(key, slice):
            bits = range(key.start, key.stop, key.step)
        elif isinstance(key, int):
            bits = [key]
        else:
            bits = key
        return bits

    def __getitem__(self, key):
        return self.variable.od.decode_bits(self.variable.data,
            self._get_bits(key))

    def __setitem__(self, key, value):
        self.variable.data = self.variable.od.encode_bits(
            self.variable.data, self._get_bits(key), value)


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
        0x060A0023: "Resource not available",
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
