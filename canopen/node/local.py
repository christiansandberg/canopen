import logging
from collections import defaultdict

from .base import BaseNode
from ..sdo import SdoServer
from ..pdo import LocalPdoNode
from ..nmt import NmtSlave
from ..emcy import EmcyProducer


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
        for subscription in self.pdo.subscriptions:
            self.network.unsubscribe(subscription)
        self.pdo.cleanup()
        self.network = None
        self.sdo.network = None
        self.pdo.network = None
        self.nmt.network = None
        self.emcy.network = None

    def add_read_callback(self, callback):
        self._read_callbacks.append(callback)

    def add_write_callback(self, callback):
        self._write_callbacks.append(callback)

    def get_data(self, index, subindex=0):
        obj = self.get_object(index, subindex)
        # Try callback
        for callback in self._read_callbacks:
            result = callback(index=index, subindex=subindex, od=obj)
            if result is not None:
                if not isinstance(result, (bytes, bytearray)):
                    result = obj.encode_raw(result)
                return result

        return obj.bytes

    def set_data(self, index, subindex, data):
        if not isinstance(data, (bytes, bytearray)):
            logger.error("Node data must be given as byte object")

        obj = self.get_object(index, subindex)

        # Store data
        obj.bytes = data

        # Try generic setter callbacks
        for callback in self._write_callbacks:
            callback(index=index, subindex=subindex, od=obj, data=data)

    def get_value(self, index, subindex=0):
        obj = self.get_object(index, subindex)

        # Try callback
        for callback in self._read_callbacks:
            result = callback(index=index, subindex=subindex, od=obj)
            if result is not None:
                return result

        return obj.raw

    def set_value(self, index, subindex, value):
        obj = self.get_object(index, subindex)

        # Store data
        obj.raw = value

        # Try generic setter callbacks
        for callback in self._write_callbacks:
            callback(index=index, subindex=subindex, od=obj, data=value)
