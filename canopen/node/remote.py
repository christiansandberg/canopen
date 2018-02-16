import logging
from ..sdo import SdoClient
from ..nmt import NmtMaster
from ..emcy import EmcyConsumer
from ..pdo import RemotePdoNode
from .base import BaseNode


logger = logging.getLogger(__name__)


class RemoteNode(BaseNode):
    """A CANopen remote node.

    :param int node_id:
        Node ID (set to None or 0 if specified by object dictionary)
    :param object_dictionary:
        Object dictionary as either a path to a file, an ``ObjectDictionary``
        or a file like object.
    :type object_dictionary: :class:`str`, :class:`canopen.ObjectDictionary`
    """

    def __init__(self, node_id, object_dictionary):
        super(RemoteNode, self).__init__(node_id, object_dictionary)

        self.sdo = SdoClient(0x600 + self.id, 0x580 + self.id,
                             self.object_dictionary)
        self.pdo = RemotePdoNode(self)
        self.nmt = NmtMaster(self.id)
        self.emcy = EmcyConsumer()

    def associate_network(self, network):
        self.network = network
        self.sdo.network = network
        self.pdo.network = network
        self.nmt.network = network
        network.subscribe(self.sdo.tx_cobid, self.sdo.on_response)
        network.subscribe(0x700 + self.id, self.nmt.on_heartbeat)
        network.subscribe(0x80 + self.id, self.emcy.on_emcy)
        self.pdo.setup()

    def remove_network(self):
        self.network.unsubscribe(self.sdo.tx_cobid)
        self.network.unsubscribe(0x700 + self.id)
        self.network.unsubscribe(0x80 + self.id)
        for pdos in (self.pdo.rx, self.pdo.tx):
            for pdo in pdos.values():
                for subscription in pdo.subscriptions:
                    self.network.unsubscribe(subscription)
        self.network = None
        self.sdo.network = None
        self.pdo.network = None
        self.nmt.network = None

    def get_data(self, index, subindex=0):
        entry = self.get_object(index, subindex)
        index = entry.index
        subindex = entry.subindex
        return self.sdo.upload(index, subindex)

    def set_data(self, index, subindex, data):
        entry = self.get_object(index, subindex)
        index = entry.index
        subindex = entry.subindex
        return self.sdo.download(index, subindex, data)

    def get_value(self, index, subindex=0):
        entry = self.get_object(index, subindex)
        index = entry.index
        subindex = entry.subindex
        return entry.decode_raw(self.sdo.upload(index, subindex))

    def set_value(self, index, subindex, value):
        entry = self.get_object(index, subindex)
        index = entry.index
        subindex = entry.subindex
        return self.sdo.download(index, subindex, entry.encode_raw(value))

    def store(self, subindex=1):
        """Store parameters in non-volatile memory.

        :param int subindex:
            1 = All parameters\n
            2 = Communication related parameters\n
            3 = Application related parameters\n
            4 - 127 = Manufacturer specific
        """
        self.sdo.download(0x1010, subindex, b"save")

    def restore(self, subindex=1):
        """Restore default parameters.

        :param int subindex:
            1 = All parameters\n
            2 = Communication related parameters\n
            3 = Application related parameters\n
            4 - 127 = Manufacturer specific
        """
        self.sdo.download(0x1011, subindex, b"load")
