import collections
import struct
import logging
import threading
import io

from . import objectdictionary
from . import common


logger = logging.getLogger(__name__)


# Command, index, subindex
SDO_STRUCT = struct.Struct("<BHB")


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
NO_MORE_DATA = 0x1
TOGGLE_BIT = 0x10


class SdoClient(collections.Mapping):
    """Handles communication with an SDO server."""

    #: Max time in seconds to wait for response from server
    RESPONSE_TIMEOUT = 0.3

    #: Max number of request retries before raising error
    MAX_RETRIES = 1

    def __init__(self, rx_cobid, tx_cobid, od):
        """
        :param int rx_cobid:
            COB-ID that the server receives on (usually 0x600 + node ID)
        :param int tx_cobid:
            COB-ID that the server responds with (usually 0x580 + node ID)
        :param canopen.ObjectDictionary od:
            Object Dictionary to use for communication
        """
        self.rx_cobid = rx_cobid
        self.tx_cobid = tx_cobid
        self.network = None
        self.od = od
        self.response = None
        self.response_received = threading.Condition()

    def on_response(self, can_id, data, timestamp):
        with self.response_received:
            self.response = bytes(data)
            self.response_received.notify_all()

    def send_request(self, sdo_request):
        retries_left = self.MAX_RETRIES
        while retries_left:
            # Wait for node to respond
            with self.response_received:
                self.response = None
                self.network.send_message(self.rx_cobid, sdo_request)
                self.response_received.wait(self.RESPONSE_TIMEOUT)

            if self.response is None:
                retries_left -= 1
            else:
                break

        if self.response is None:
            raise SdoCommunicationError("No SDO response received")
        if retries_left != self.MAX_RETRIES:
            logger.warning("There were some issues while communicating with the node")
        res_command, = struct.unpack("B", self.response[0:1])
        if res_command == RESPONSE_ABORTED:
            abort_code, = struct.unpack("<L", self.response[4:8])
            raise SdoAbortedError(abort_code)
        else:
            return self.response

    def upload(self, index, subindex):
        """May be called to make a read operation without an Object Dictionary.

        :param int index:
            Index of object to read.
        :param int subindex:
            Sub-index of object to read.

        :return: A data object.
        :rtype: bytes

        :raises canopen.SdoCommunicationError:
            On unexpected response or timeout.
        :raises canopen.SdoAbortedError:
            When node responds with an error.
        """
        with ReadableStream(self, index, subindex) as fp:
            return fp.read()

    def download(self, index, subindex, data, force_segment=False):
        """May be called to make a write operation without an Object Dictionary.

        :param int index:
            Index of object to write.
        :param int subindex:
            Sub-index of object to write.
        :param bytes data:
            Data to be written.
        :param bool force_segment:
            Force use of segmented transfer regardless of data size.

        :raises canopen.SdoCommunicationError:
            On unexpected response or timeout.
        :raises canopen.SdoAbortedError:
            When node responds with an error.
        """
        raw_stream = WritableStream(self, index, subindex, len(data), force_segment)
        with io.BufferedWriter(raw_stream, 7) as fp:
            fp.write(data)

    def __getitem__(self, index):
        entry = self.od[index]
        if isinstance(entry, objectdictionary.Variable):
            return Variable(self, entry)
        elif isinstance(entry, objectdictionary.Array):
            return Array(self, entry)
        elif isinstance(entry, objectdictionary.Record):
            return Record(self, entry)

    def __iter__(self):
        return iter(self.od)

    def __len__(self):
        return len(self.od)

    def __contains__(self, key):
        return key in self.od


class Record(collections.Mapping):

    def __init__(self, sdo_node, od):
        self.sdo_node = sdo_node
        self.od = od

    def __getitem__(self, subindex):
        return Variable(self.sdo_node, self.od[subindex])

    def __iter__(self):
        return iter(self.od)

    def __len__(self):
        return len(self.od)

    def __contains__(self, subindex):
        return subindex in self.od


class Array(collections.Mapping):

    def __init__(self, sdo_node, od):
        self.sdo_node = sdo_node
        self.od = od

    def __getitem__(self, subindex):
        return Variable(self.sdo_node, self.od[subindex])

    def __iter__(self):
        return iter(range(1, len(self) + 1))

    def __len__(self):
        return self[0].raw

    def __contains__(self, subindex):
        return 0 <= subindex <= len(self)


class Variable(common.Variable):
    """Access object dictionary variable values using SDO protocol."""

    def __init__(self, sdo_node, od):
        self.sdo_node = sdo_node
        common.Variable.__init__(self, od)

    def get_data(self):
        return self.sdo_node.upload(self.od.index, self.od.subindex)

    def set_data(self, data):
        force_segment = self.od.data_type == objectdictionary.DOMAIN
        self.sdo_node.download(self.od.index, self.od.subindex, data, force_segment)

    def read(self, fmt="raw"):
        """Alternative way of reading using a function instead of attributes.

        May be useful for asynchronous reading.

        :param str fmt:
            How to return the value
             - 'raw'
             - 'phys'
             - 'desc'

        :returns:
            The value of the variable.
        """
        if fmt == "raw":
            return self.raw
        elif fmt == "phys":
            return self.phys
        elif fmt == "desc":
            return self.desc

    def write(self, value, fmt="raw"):
        """Alternative way of writing using a function instead of attributes.

        May be useful for asynchronous writing.

        :param str fmt:
            How to write the value
             - 'raw'
             - 'phys'
             - 'desc'
        """
        if fmt == "raw":
            self.raw = value
        elif fmt == "phys":
            self.phys = value
        elif fmt == "desc":
            self.desc = value

    def open(self, mode="rb", encoding="ascii", buffering=112):
        """Open the data stream as a file like object.

        :param str mode:
            ========= ==========================================================
            Character Meaning
            --------- ----------------------------------------------------------
            'r'       open for reading (default)
            'w'       open for writing
            'b'       binary mode (default)
            't'       text mode
            ========= ==========================================================
        :param str encoding:
            The str name of the encoding used to decode or encode the file.
            This will only be used in text mode.
        :param int buffering:
            An optional integer used to set the buffering policy. Pass 0 to
            switch buffering off (only allowed in binary mode), 1 to select line
            buffering (only usable in text mode), and an integer > 1 to indicate
            the size in bytes of a fixed-size chunk buffer.

        :returns:
            A file like object.
        """
        if "r" in mode:
            RawStreamCls = ReadableStream
            BufferedStreamCls = io.BufferedReader
        if "w" in mode:
            RawStreamCls = WritableStream
            BufferedStreamCls = io.BufferedWriter
        raw_stream = RawStreamCls(self.sdo_node, self.od.index, self.od.subindex)
        if buffering == 0:
            return raw_stream
        # Line buffering is not supported by BufferedReader
        buffer_size = buffering if buffering > 1 else io.DEFAULT_BUFFER_SIZE
        buffered_stream = BufferedStreamCls(raw_stream, buffer_size=buffer_size)
        if "b" not in mode:
            # Text mode
            line_buffering = buffering == 1
            return io.TextIOWrapper(buffered_stream, encoding,
                                    line_buffering=line_buffering)
        return buffered_stream


class ReadableStream(io.RawIOBase):
    """File like object for reading from a variable."""

    #: Total size of data or ``None`` if not specified
    size = None

    def __init__(self, sdo_client, index, subindex=0):
        """
        :param canopen.sdo.SdoClient sdo_client:
            The SDO client to use for reading.
        :param int index:
            Object dictionary index to read from.
        :param int subindex:
            Object dictionary sub-index to read from.
        """
        self._done = False
        self.sdo_client = sdo_client
        self._toggle = 0

        logger.debug("Reading 0x%X:%d from node %d", index, subindex,
                     sdo_client.rx_cobid - 0x600)
        request = SDO_STRUCT.pack(REQUEST_UPLOAD, index, subindex)
        request += b"\x00\x00\x00\x00"
        response = sdo_client.send_request(request)
        res_command, res_index, res_subindex = SDO_STRUCT.unpack(response[0:4])
        res_data = response[4:8]

        if res_command & 0xE0 != RESPONSE_UPLOAD:
            raise SdoCommunicationError("Unexpected response 0x%02X" % res_command)

        # Check that the message is for us
        if res_index != index or res_subindex != subindex:
            raise SdoCommunicationError((
                "Node returned a value for 0x{:X}:{:d} instead, "
                "maybe there is another SDO client communicating "
                "on the same SDO channel?").format(res_index, res_subindex))

        self.exp_data = None
        if res_command & EXPEDITED:
            # Expedited upload
            if res_command & SIZE_SPECIFIED:
                self.size = 4 - ((res_command >> 2) & 0x3)
            else:
                self.size = 4
            self.exp_data = res_data[:self.size]
        elif res_command & SIZE_SPECIFIED:
            self.size, = struct.unpack("<L", res_data)
            logger.debug("Using segmented transfer of %d bytes", self.size)
        else:
            logger.debug("Using segmented transfer")

    def read(self, size=-1):
        """Read one segment which may be up to 7 bytes.

        :param int size:
            If size is -1, all data will be returned. Other values are ignored.

        :returns: 1 - 7 bytes of data or no bytes if EOF.
        :rtype: bytes
        """
        if self._done:
            return b""
        if self.exp_data is not None:
            self._done = True
            return self.exp_data
        if size is None or size < 0:
            return self.readall()

        command = REQUEST_SEGMENT_UPLOAD
        command |= self._toggle
        request = bytearray(8)
        request[0] = command
        response = self.sdo_client.send_request(request)
        res_command, = struct.unpack("B", response[0:1])
        if res_command & 0xE0 != RESPONSE_SEGMENT_UPLOAD:
            raise SdoCommunicationError("Unexpected response 0x%02X" % res_command)
        last_byte = 8 - ((res_command >> 1) & 0x7)
        if res_command & NO_MORE_DATA:
            self._done = True
        self._toggle ^= TOGGLE_BIT
        return response[1:last_byte]

    def readinto(self, b):
        """
        Read bytes into a pre-allocated, writable bytes-like object b,
        and return the number of bytes read.
        """
        data = self.read(7)
        b[:len(data)] = data
        return len(data)

    def readable(self):
        return True


class WritableStream(io.RawIOBase):
    """File like object for writing to a variable."""

    def __init__(self, sdo_client, index, subindex=0, size=None, force_segment=False):
        """
        :param canopen.sdo.SdoClient sdo_client:
            The SDO client to use for communication.
        :param int index:
            Object dictionary index to read from.
        :param int subindex:
            Object dictionary sub-index to read from.
        :param int size:
            Size of data in number of bytes if known in advance.
        :param bool force_segment:
            Force use of segmented transfer regardless of size.
        """
        self.sdo_client = sdo_client
        self.size = size
        self.pos = 0
        self._toggle = 0
        self._exp_header = None
        self._done = False

        if size is None or size > 4 or force_segment:
            # Initiate segmented download
            command = REQUEST_DOWNLOAD
            if size is not None:
                command |= SIZE_SPECIFIED
                size_data = struct.pack("<L", size)
            else:
                size_data = b"\x00\x00\x00\x00"
            request = SDO_STRUCT.pack(command, index, subindex) + size_data
            response = sdo_client.send_request(request)
            res_command, = struct.unpack("B", response[0:1])
            if res_command != RESPONSE_DOWNLOAD:
                raise SdoCommunicationError(
                    "Unexpected response 0x%02X" % res_command)
        else:
            # Expedited download
            # Prepare header (first 4 bytes in CAN message)
            command = REQUEST_DOWNLOAD | EXPEDITED | SIZE_SPECIFIED
            command |= (4 - size) << 2
            self._exp_header = SDO_STRUCT.pack(command, index, subindex)

    def write(self, b):
        """
        Write the given bytes-like object, b, to the SDO server, and return the
        number of bytes written. This will be at most 7 bytes.
        """
        if self._exp_header is not None:
            # Expedited download
            if len(b) < self.size:
                # Not enough data provided
                return 0
            # Expedited download
            request = bytearray(self._exp_header) + b
            bytes_sent = len(b)
            expected_response = RESPONSE_DOWNLOAD
            self._done = True
        else:
            # Segmented download
            request = bytearray(8)
            command = REQUEST_SEGMENT_DOWNLOAD
            # Add toggle bit
            command |= self._toggle
            self._toggle ^= TOGGLE_BIT
            # Can send up to 7 bytes at a time
            bytes_sent = min(len(b), 7)
            request[1:8] = b[0:bytes_sent]
            if self.size is not None and self.pos + bytes_sent >= self.size:
                # No more data after this message
                command |= NO_MORE_DATA
                self._done = True
            # Specify number of bytes that do not contain segment data
            command |= (7 - bytes_sent) << 1
            request[0] = command
            expected_response = RESPONSE_SEGMENT_DOWNLOAD
        response = self.sdo_client.send_request(request.ljust(8, b"\x00"))
        res_command, = struct.unpack("B", response[0:1])
        if res_command & 0xE0 != expected_response:
            raise SdoCommunicationError(
                "Unexpected response 0x%02X (expected 0x%02X)" % (
                    res_command, expected_response))
        # Advance position
        self.pos += bytes_sent
        if self.size is not None and self.pos > self.size:
            raise ValueError("Expected data size exceeded")
        return bytes_sent

    def close(self):
        """Closes the stream.

        An empty segmented SDO message may be sent saying there is no more data.
        """
        super(WritableStream, self).close()
        if not self._done:
            command = REQUEST_SEGMENT_DOWNLOAD | NO_MORE_DATA
            command |= self._toggle
            # No data in this message
            command |= 7 << 1
            request = bytearray(8)
            request[0] = command
            self.sdo_client.send_request(request)

    def writable(self):
        return True


class SdoError(Exception):
    pass


class SdoAbortedError(SdoError):
    """SDO abort exception."""

    CODES = {
        0x05030000: "SDO toggle bit error",
        0x05040000: "Timeout of transfer communication detected",
        0x05040001: "Unknown SDO command specified",
        0x05040003: "Invalid sequence number",
        0x06010000: "Unsupported access to an object",
        0x06010001: "Attempt to read a write only object",
        0x06010002: "Attempt to write a read only object",
        0x06020000: "Object does not exist",
        0x06040042: "PDO length exceeded",
        0x06060000: "Access failed due to a hardware error",
        0x06070010: "Data type and length code do not match",
        0x06090011: "Subindex does not exist",
        0x06090030: "Value range of parameter exceeded",
        0x060A0023: "Resource not available",
        0x08000000: "General error",
        0x08000021: ("Data can not be transferred or stored to the application "
                     "because of local control"),
        0x08000022: ("Data can not be transferred or stored to the application "
                     "because of the present device state")
    }

    def __init__(self, code):
        #: Abort code
        self.code = code

    def __str__(self):
        text = "Code 0x{:08X}".format(self.code)
        if self.code in self.CODES:
            text = text + ", " + self.CODES[self.code]
        return text


class SdoCommunicationError(SdoError):
    """No or unexpected response from slave."""
