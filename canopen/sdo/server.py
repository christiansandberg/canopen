import logging
import collections

from .. import objectdictionary
from .. import variable
from .constants import *
from .exceptions import *


logger = logging.getLogger(__name__)


class SdoServer(collections.Mapping):
    """Creates an SDO server."""

    def __init__(self, rx_cobid, tx_cobid, node):
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
        self.od = node.object_dictionary
        self._callbacks = node.callbacks
        self._data_store = node.data_store
        self._buffer = None
        self._toggle = 0
        self._index = None
        self._subindex = None

    def on_request(self, can_id, data, timestamp):
        command, = struct.unpack_from("B", data, 0)
        ccs = command & 0xE0

        try:
            if ccs == REQUEST_UPLOAD:
                self.init_upload(data)
            elif ccs == REQUEST_SEGMENT_UPLOAD:
                self.segmented_upload(command)
            elif ccs == REQUEST_DOWNLOAD:
                self.init_download(data)
            elif ccs == REQUEST_SEGMENT_DOWNLOAD:
                self.segmented_download(command, data)
        except SdoAbortedError as exc:
            self.abort(exc.code)
        except KeyError as exc:
            self.abort(0x06020000)
        except Exception as exc:
            self.abort()
            logger.exception(exc)

    def init_upload(self, request):
        _, index, subindex = SDO_STRUCT.unpack_from(request)
        self._index = index
        self._subindex = subindex
        res_command = RESPONSE_UPLOAD | SIZE_SPECIFIED
        response = bytearray(8)

        data = self.upload(index, subindex)
        size = len(data)
        if size <= 4:
            logger.info("Expedited upload for 0x%X:%d", index, subindex)
            res_command |= EXPEDITED
            res_command |= (4 - size) << 2
            response[4:4 + size] = data
        else:
            logger.info("Initiating segmented upload for 0x%X:%d", index, subindex)
            struct.pack_into("<L", response, 4, size)
            self._buffer = bytearray(data)
            self._toggle = 0

        SDO_STRUCT.pack_into(response, 0, res_command, index, subindex)
        self.send_response(response)

    def segmented_upload(self, command):
        if command & TOGGLE_BIT != self._toggle:
            # Toggle bit mismatch
            raise SdoAbortedError(0x05030000)
        data = self._buffer[:7]
        size = len(data)

        # Remove sent data from buffer
        del self._buffer[:7]

        res_command = RESPONSE_SEGMENT_UPLOAD
        # Add toggle bit
        res_command |= self._toggle
        # Add nof bytes not used
        res_command |= (7 - size) << 1
        if not self._buffer:
            # Nothing left in buffer
            res_command |= NO_MORE_DATA << 1
        # Toggle bit for next message
        self._toggle ^= TOGGLE_BIT

        response = bytearray(8)
        response[0] = res_command
        response[1:1 + size] = data
        self.send_response(response)

    def init_download(self, request):
        command, index, subindex = SDO_STRUCT.unpack_from(request)
        self._index = index
        self._subindex = subindex
        res_command = RESPONSE_DOWNLOAD
        response = bytearray(8)

        if command & EXPEDITED:
            logger.info("Expedited download for 0x%X:%d", index, subindex)
            if command & SIZE_SPECIFIED:
                size = 4 - ((command >> 2) & 0x3)
            else:
                size = 4
            self.download(index, subindex, request[4:4 + size])
        else:
            logger.info("Initiating segmented download for 0x%X:%d", index, subindex)
            if command & SIZE_SPECIFIED:
                size, = struct.unpack_from("<L", request, 4)
                logger.info("Size is %d bytes", size)
            self._buffer = bytearray()
            self._toggle = 0

        SDO_STRUCT.pack_into(response, 0, res_command, index, subindex)
        self.send_response(response)

    def segmented_download(self, command, request):
        if command & TOGGLE_BIT != self._toggle:
            # Toggle bit mismatch
            raise SdoAbortedError(0x05030000)
        last_byte = 8 - ((command >> 1) & 0x7)
        self._buffer.extend(request[1:last_byte])

        if command & NO_MORE_DATA:
            self.download(self._index, self._subindex, self._buffer)

        res_command = RESPONSE_SEGMENT_DOWNLOAD
        # Add toggle bit
        res_command |= self._toggle
        # Toggle bit for next message
        self._toggle ^= TOGGLE_BIT

        response = bytearray(8)
        response[0] = res_command
        self.send_response(response)

    def send_response(self, response):
        self.network.send_message(self.tx_cobid, response)

    def abort(self, abort_code=0x08000000):
        """Abort current transfer."""
        data = struct.pack("<BHBL", RESPONSE_ABORTED,
                           self._index, self._subindex, abort_code)
        self.send_response(data)
        # logger.error("Transfer aborted with code 0x{:08X}".format(abort_code))

    def upload(self, index, subindex):
        """May be called to make a read operation without an Object Dictionary.

        :param int index:
            Index of object to read.
        :param int subindex:
            Sub-index of object to read.

        :return: A data object.
        :rtype: bytes

        :raises canopen.SdoAbortedError:
            When node responds with an error.
        """
        obj = self._find_object(index, subindex)

        # Try callback
        for callback in self._callbacks:
            result = callback(index=index, subindex=subindex, od=obj, data=None)
            if result is not None:
                return obj.encode_raw(result)

        # Try stored data
        try:
            return self._data_store[index][subindex]
        except KeyError:
            # Try default value
            if obj.default is None:
                # Resource not available
                raise SdoAbortedError(0x060A0023)
            return obj.encode_raw(obj.default)

    def download(self, index, subindex, data):
        """May be called to make a write operation without an Object Dictionary.

        :param int index:
            Index of object to write.
        :param int subindex:
            Sub-index of object to write.
        :param bytes data:
            Data to be written.

        :raises canopen.SdoAbortedError:
            When node responds with an error.
        """
        obj = self._find_object(index, subindex)

        # Try callback
        for callback in self._callbacks:
            status = callback(index=index, subindex=subindex, od=obj, data=data)
            if status:
                break

        # Store data
        self._data_store.setdefault(index, {})
        self._data_store[index][subindex] = bytes(data)

    def _find_object(self, index, subindex):
        if index not in self.od:
            # Index does not exist
            raise SdoAbortedError(0x06020000)
        obj = self.od[index]
        if not isinstance(obj, objectdictionary.Variable):
            # Group or array
            if subindex not in obj:
                # Subindex does not exist
                raise SdoAbortedError(0x06090011)
            obj = obj[subindex]
        return obj

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


class Variable(variable.Variable):
    """Access object dictionary variable values using SDO protocol."""

    def __init__(self, sdo_node, od):
        self.sdo_node = sdo_node
        variable.Variable.__init__(self, od)

    def get_data(self):
        return self.sdo_node.upload(self.od.index, self.od.subindex)

    def set_data(self, data):
        self.sdo_node.download(self.od.index, self.od.subindex, data)
