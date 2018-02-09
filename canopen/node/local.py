import logging
from collections import defaultdict

from .base import BaseNode
from ..sdo import SdoServer, SdoAbortedError
from ..pdo import LocalPdoNode
from ..nmt import NmtSlave
from ..emcy import EmcyProducer
from .. import objectdictionary


logger = logging.getLogger(__name__)


class LocalNode(BaseNode):

    def __init__(self, node_id, object_dictionary):
        super(LocalNode, self).__init__(node_id, object_dictionary)

        self._read_callbacks = []
        self._write_callbacks = []

        self.sdo = SdoServer(0x600 + self.id, 0x580 + self.id, self)
        self.pdo = LocalPdoNode(self)
        self.nmt = NmtSlave(self.id, self)
        # Let self.nmt handle writes for 0x1017
        self.add_write_callback(self.nmt.on_write)
        self.emcy = EmcyProducer(0x80 + self.id)

    def associate_network(self, network):
        self.network = network
        self.sdo.network = network
        self.pdo.network = network
        self.nmt.network = network
        self.emcy.network = network
        network.subscribe(self.sdo.rx_cobid, self.sdo.on_request)
        network.subscribe_nmt_cmd(self.id, self.nmt.on_command)
        self.pdo.setup()

    def remove_network(self):
        self.network.unsubscribe_all(self.sdo.rx_cobid)
        self.network = None
        self.sdo.network = None
        self.pdo.network = None
        self.nmt.network = None
        self.emcy.network = None

    def add_read_callback(self, callback):
        self._read_callbacks.append(callback)

    def add_write_callback(self, callback):
        self._write_callbacks.append(callback)

    def get_data(self, index, subindex):
        obj = self._find_object(index, subindex)

        # Try callback
        for callback in self._read_callbacks:
            result = callback(index=index, subindex=subindex, od=obj)
            if result is not None:
                return obj.encode_raw(result)

        # Try stored data
        try:
            return self.data_store[index][subindex]
        except KeyError:
            # Try default value
            if obj.default is None:
                # Resource not available
                logger.info("Resource unavailable for 0x%X:%d", index, subindex)
                raise SdoAbortedError(0x060A0023)
            return obj.encode_raw(obj.default)

    def set_data(self, index, subindex, data):
        if not isinstance(data, (bytes, bytearray)):
            logger.error("Node data must be given as byte object")

        obj = self._find_object(index, subindex)

        # Store data
        self.data_store.setdefault(index, {})
        self.data_store[index][subindex] = data

        # Execute the data change traps
        for callback in self.data_store_traps[(index, subindex)]:
            callback([(index, subindex, data)])

        # Try generic setter callbacks
        for callback in self._write_callbacks:
            callback(index=index, subindex=subindex, od=obj, data=data)

    def data_transaction(self, transaction):
        """Change the internal data atomically. The net result of this method
        is identical to calling `set_data` for every data change found in the
        transaction object. The difference is that the callbacks are only
        called once at the end.

        :param transaction: A list of (index, subindex, new_byte_data) tuples
        """
        callback_infos = defaultdict(list)
        for index, subindex, data in transaction:
            self.data_store.setdefault(index, {})
            self.data_store[index][subindex] = data
            for callback in self.data_store_traps[(index, subindex)]:
                callback_infos[callback].append((index, subindex, data))

        # Now call the callback, but once with the info about all changes of
        # interest
        for callback, callback_args in callback_infos.items():
            callback(callback_args)

    def _find_object(self, index, subindex):
        if index not in self.object_dictionary:
            # Index does not exist
            raise SdoAbortedError(0x06020000)
        obj = self.object_dictionary[index]
        if not isinstance(obj, objectdictionary.Variable):
            # Group or array
            if subindex not in obj:
                # Subindex does not exist
                raise SdoAbortedError(0x06090011)
            obj = obj[subindex]
        return obj
