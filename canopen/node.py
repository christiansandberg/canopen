from .sdo import SdoNode
from .nmt import NmtNode
from . import objectdictionary


SDO_RESPONSE = 0x580
SDO_REQUEST = 0x600
HEARTBEAT = 0x700


class Node(object):

    def __init__(self, node_id, object_dictionary):
        self.id = node_id
        self.network = None
        self.service_callbacks = {}

        self.object_dictionary = objectdictionary.import_any(object_dictionary)

        self.sdo = SdoNode(node_id, self.object_dictionary)
        self.sdo.parent = self
        self.register_service(SDO_RESPONSE, self.sdo.on_response)

        self.nmt = NmtNode(node_id)
        self.nmt.parent = self
        self.register_service(HEARTBEAT, self.nmt.on_heartbeat)

    def register_service(self, cob_id, callback):
        self.service_callbacks[cob_id] = callback

    def on_message(self, can_id, data):
        fn_code = can_id & 0x780
        if fn_code in self.service_callbacks:
            self.service_callbacks[fn_code](can_id, data)

