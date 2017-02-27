from .sdo import SdoClient
from .nmt import NmtMaster
from .emcy import EmcyConsumer
from .pdo import PdoNode
from . import objectdictionary


class Node(object):
    """A CANopen slave node.

    :param int node_id:
        Node ID (set to None or 0 if specified by object dictionary)
    :param object_dictionary:
        Object dictionary as either a path to a file, an ``ObjectDictionary``
        or a file like object.
    :type object_dictionary: :class:`str`, :class:`canopen.ObjectDictionary`
    """

    def __init__(self, node_id, object_dictionary):
        self.network = None

        if not isinstance(object_dictionary,
                          objectdictionary.ObjectDictionary):
            object_dictionary = objectdictionary.import_od(
                object_dictionary, node_id)
        self.object_dictionary = object_dictionary

        self.id = node_id or self.object_dictionary.node_id

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
