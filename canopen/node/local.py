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
        self.network.unsubscribe(self.sdo.rx_cobid)
        self.network.unsubscribe_nmt_cmd(self.id)
        for pdos in (self.pdo.rx, self.pdo.tx):
            for pdo in pdos.values():
                for subscription in pdo.subscriptions:
                    self.network.unsubscribe(subscription)
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
        obj = self.get_object(index, subindex)

        # Try callback
        for callback in self._read_callbacks:
            result = callback(index=index, subindex=subindex, od=obj)
            if result is not None:
                return obj.encode_raw(result)

        return obj.raw

    def set_data(self, index, subindex, data):
        if not isinstance(data, (bytes, bytearray)):
            logger.error("Node data must be given as byte object")

        obj = self.get_object(index, subindex)

        # Store data
        obj.raw = data

        # Execute the data change traps
        for callback in self.data_store_traps[(index, subindex)]:
            callback([(index, subindex, data)])

        # Try generic setter callbacks
        for callback in self._write_callbacks:
            callback(index=index, subindex=subindex, od=obj, data=data)

    def get_value(self, index, subindex):
        obj = self.get_object(index, subindex)

        # Try callback
        for callback in self._read_callbacks:
            result = callback(index=index, subindex=subindex, od=obj)
            if result is not None:
                return obj.encode_raw(result)

        return obj.value

    def set_value(self, index, subindex, value):
        obj = self.get_object(index, subindex)

        # Store data
        obj.value = value

        # Execute the data change traps
        for callback in self.data_store_traps[(index, subindex)]:
            callback([(index, subindex, value)])

        # Try generic setter callbacks
        for callback in self._write_callbacks:
            callback(index=index, subindex=subindex, od=obj, data=value)

    def data_transaction(self, transaction):
        """Change the internal data atomically. The net result of this method
        is identical to calling `set_data` for every data change found in the
        transaction object. The difference is that the callbacks are only
        called once at the end.

        :param transaction: A list of (index, subindex, new_byte_data) tuples
        """
        callback_infos = defaultdict(list)
        for index, subindex, data in transaction:
            self.set_data(index, subindex, data)
            for callback in self.data_store_traps[(index, subindex)]:
                callback_infos[callback].append((index, subindex, data))

        # Now call the callback, but once with the info about all changes of
        # interest
        for callback, callback_args in callback_infos.items():
            callback(callback_args)

    def get_object(self, index, subindex):
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
