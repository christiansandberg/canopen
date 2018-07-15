from ..sdo import SdoClient
from ..nmt import NmtMaster
from ..emcy import EmcyConsumer
from ..pdo import PdoNode
from .base import BaseNode


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

        #: Enable WORKAROUND for reversed PDO mapping entries
        self.curtis_hack = False

        self.sdo = SdoClient(0x600 + self.id, 0x580 + self.id, object_dictionary)
        self.pdo = PdoNode(self)
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

    def remove_network(self):
        self.network.unsubscribe(self.sdo.tx_cobid)
        self.network.unsubscribe(0x700 + self.id)
        self.network.unsubscribe(0x80 + self.id)
        self.network = None
        self.sdo.network = None
        self.pdo.network = None
        self.nmt.network = None

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
