from .sdo import SdoNode
from .nmt import NmtNode
from .emcy import EmcyNode
from .pdo import PdoNode
from . import objectdictionary


EMCY = 0x80
SDO_RESPONSE = 0x580
HEARTBEAT = 0x700


class Node(object):

    def __init__(self, node_id=1, object_dictionary=None):
        self.id = node_id
        self.network = None
        self.object_dictionary = objectdictionary.ObjectDictionary()
        self.service_callbacks = {}
        self.message_callbacks = []

        if object_dictionary:
            self.set_object_dictionary(object_dictionary)

        self.sdo = SdoNode(self, node_id)
        self.register_service(SDO_RESPONSE, self.sdo.on_response)

        self.pdo = PdoNode(self)
        self.add_callback(self.pdo.on_message)

        self.nmt = NmtNode(self)
        self.register_service(HEARTBEAT, self.nmt.on_heartbeat)

        self.emcy = EmcyNode()
        self.register_service(EMCY, self.emcy.on_emcy)

    def add_callback(self, callback):
        self.message_callbacks.append(callback)

    def set_node_id(self, node_id):
        self.id = node_id
        self.sdo.id = node_id

    def set_object_dictionary(self, object_dictionary):
        assert object_dictionary, "An Object Dictionary file has not been specified"
        if not isinstance(object_dictionary, objectdictionary.ObjectDictionary):
            object_dictionary = objectdictionary.import_any(object_dictionary)
        self.object_dictionary = object_dictionary

    def set_sdo_channel(self, node_id):
        self.sdo.id = node_id

    def register_service(self, cob_id, callback):
        self.service_callbacks[cob_id] = callback

    def on_message(self, can_id, data, timestamp):
        fn_code = can_id & 0x780
        if fn_code in self.service_callbacks:
            self.service_callbacks[fn_code](can_id, data, timestamp)
