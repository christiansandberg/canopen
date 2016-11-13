from .sdo import SdoClient
from .nmt import NmtMaster
from .emcy import EmcyConsumer
from .pdo import PdoNode
from . import objectdictionary


class Node(object):
    """A CANopen slave node."""

    def __init__(self, node_id, object_dictionary, network):
        """
        :param int node_id:
            Node ID
        :param object_dictionary:
            Object dictionary as either a path to a file or an object.
        :type object_dictionary: :class:`str`, :class:`canopen.ObjectDictionary`
        """
        #: Node ID
        self.id = node_id
        #: :class:`canopen.Network` owning the node
        self.network = network

        if not isinstance(object_dictionary,
                          objectdictionary.ObjectDictionary):
            object_dictionary = objectdictionary.import_od(
                object_dictionary, node_id)
        #: :class:`canopen.ObjectDictionary` associated with the node
        self.object_dictionary = object_dictionary

        self.sdo = SdoClient(network, node_id, object_dictionary)
        network.subscribe(0x580 + node_id, self.sdo.on_response)

        self.pdo = PdoNode(network, object_dictionary)

        self.nmt = NmtMaster(network, node_id)
        network.subscribe(0x700 + node_id, self.nmt.on_heartbeat)
        network.subscribe(0x0 + node_id, self.nmt.on_nmt_command)
        network.subscribe(0x0, self.nmt.on_nmt_command)

        self.emcy = EmcyConsumer()
        network.subscribe(0x80 + node_id, self.emcy.on_emcy)
