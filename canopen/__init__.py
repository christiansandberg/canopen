import collections
import can
from canopen import objectdictionary, sdo, pdo, nmt


SDO_RESPONSE = 0x580
SDO_REQUEST = 0x600


class Network(collections.Mapping):

    def __init__(self):
        self.bus = None
        self.dispatcher = MessageDispatcher(self)
        self.notifier = None
        self.nodes = {}

    def connect(self, *args, **kwargs):
        self.bus = can.interface.Bus(*args, **kwargs)
        self.notifier = can.Notifier(self.bus, [self.dispatcher], 1)

    def disconnect(self):
        self.bus.shutdown()
        self.notifier.running.clear()

    def add_node(self, node, object_dictionary=None):
        if isinstance(node, int):
            node = Node(node, object_dictionary)
        node.network = self
        self.nodes[node.id] = node
        return node

    def send_message(self, can_id, data):
        if not self.bus:
            raise Exception("A connection to the CAN bus has not been made")
        msg = can.Message(extended_id=False, arbitration_id=can_id, data=data)
        self.bus.send(msg)

    def __getitem__(self, node_id):
        return self.nodes[node_id]

    def __iter__(self):
        return iter(self.nodes)

    def __len__(self):
        return len(self.nodes)

    def __contains__(self, node_id):
        return node_id in self.nodes


class Node(object):

    def __init__(self, node_id, object_dictionary):
        self.id = node_id
        self.network = None
        self.service_callbacks = {}

        self.object_dictionary = objectdictionary.import_any(object_dictionary)

        self.sdo = sdo.Node(node_id, self.object_dictionary)
        self.sdo.parent = self
        self.register_service(SDO_RESPONSE, self.sdo.on_response)

    def register_service(self, cob_id, callback):
        self.service_callbacks[cob_id] = callback

    def on_message(self, msg):
        fn_code = msg.arbitration_id & 0x780
        if fn_code in self.service_callbacks:
            self.service_callbacks[fn_code](msg)


class MessageDispatcher(can.Listener):

    def __init__(self, network):
        self.network = network

    def on_message_received(self, msg):
        if msg.id_type:
            # Ignore all 29-bit messages
            return

        node_id = msg.arbitration_id & 0x7F
        if node_id in self.network:
            self.network[node_id].on_message(msg)
