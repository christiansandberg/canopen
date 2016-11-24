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
        Object dictionary as either a path to a file or an object.
    :type object_dictionary: :class:`str`, :class:`canopen.ObjectDictionary`
    """

    def __init__(self, node_id, object_dictionary, network):
        self.network = network

        if not isinstance(object_dictionary,
                          objectdictionary.ObjectDictionary):
            object_dictionary = objectdictionary.import_od(
                object_dictionary, node_id)
        self.object_dictionary = object_dictionary

        self.id = node_id or self.object_dictionary.node_id

        self.sdo = SdoClient(network, node_id, object_dictionary)
        network.subscribe(0x580 + node_id, self.sdo.on_response)

        self.pdo = PdoNode(network, object_dictionary)

        self.nmt = NmtMaster(network, node_id)
        network.subscribe(0x700 + node_id, self.nmt.on_heartbeat)
        network.subscribe(0x0, self.nmt.on_nmt_command)

        self.emcy = EmcyConsumer()
        network.subscribe(0x80 + node_id, self.emcy.on_emcy)
