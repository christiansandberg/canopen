from .sdo import SdoClient
from .nmt import NmtMaster
from .emcy import EmcyConsumer
from .pdo import PdoNode
from . import objectdictionary


EMCY = 0x80
SDO_RESPONSE = 0x580
HEARTBEAT = 0x700


class Node(object):
    """A CANopen slave node.

    :param int node_id:
        Node ID
    :param object_dictionary:
        Object dictionary as either a path to a file or an object.
    :type object_dictionary: :class:`str`, :class:`canopen.ObjectDictionary`
    """

    def __init__(self, node_id=1, object_dictionary=None):
        #: Node ID
        self.id = node_id
        #: :class:`canopen.Network` owning the node
        self.network = None
        #: :class:`canopen.ObjectDictionary` associated with the node
        self.object_dictionary = objectdictionary.ObjectDictionary()
        self.service_callbacks = {}
        self.message_callbacks = []

        if object_dictionary:
            self.set_object_dictionary(object_dictionary)

        self.sdo = SdoClient(self, node_id)
        self.register_service(SDO_RESPONSE, self.sdo.on_response)

        self.pdo = PdoNode(self)
        self.add_callback(self.pdo.on_message)

        self.nmt = NmtMaster(self)
        self.register_service(HEARTBEAT, self.nmt.on_heartbeat)

        self.emcy = EmcyConsumer()
        self.register_service(EMCY, self.emcy.on_emcy)

    def add_callback(self, callback):
        self.message_callbacks.append(callback)

    def set_node_id(self, node_id):
        self.id = node_id
        self.sdo.id = node_id

    def set_object_dictionary(self, object_dictionary):
        """Sets the object dictionary for the node.

        :param object_dictionary:
            Object dictionary as either a path to a file or an object.
        :type object_dictionary: :class:`str`, :class:`canopen.ObjectDictionary`
        """
        assert object_dictionary, "An Object Dictionary file has not been specified"
        if not isinstance(object_dictionary,
                          objectdictionary.ObjectDictionary):
            object_dictionary = objectdictionary.import_od(object_dictionary)
        self.object_dictionary = object_dictionary

    def set_sdo_channel(self, node_id):
        self.sdo.id = node_id

    def register_service(self, cob_id, callback):
        self.service_callbacks[cob_id] = callback

    def on_message(self, can_id, data, timestamp):
        fn_code = can_id & 0x780
        if fn_code in self.service_callbacks:
            self.service_callbacks[fn_code](can_id, data, timestamp)
