import collections
import can
import canopen
from canopen import objectdictionary, sdo, pdo, nmt


SDO_RESPONSE = 0x580
SDO_REQUEST = 0x600


class Network(collections.Mapping):

    def __init__(self):
        self.bus = None
        self.nodes = {}

    def connect(self, *args, **kwargs):
        self.bus = can.interface.Bus(*args, **kwargs)
        self.dispatcher = MessageDispatcher(self)
        self.notifier = can.Notifier(self.bus, [self.dispatcher], 1)

    def add_node(self, node_id, object_dictionary=None):
        node = Node(node_id, self, object_dictionary)
        self.nodes[node_id] = node
        return node

    def send_message(self, can_id, data):
        msg = can.Message(extended_id=False, arbitration_id=can_id, data=data)
        print(msg)
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

    def __init__(self, node_id, network, object_dictionary):
        self.object_dictionary = objectdictionary.import_any(object_dictionary)
        self.sdo = canopen.sdo.Node(node_id, self.object_dictionary, network)

    def on_message(self, msg):
        fn_code = msg.arbitration_id & 0x780
        if fn_code == SDO_RESPONSE:
            self.sdo.on_response(msg)


class MessageDispatcher(can.Listener):

    def __init__(self, network):
        self.network = network

    def on_message_received(self, msg):
        if msg.id_type:
            return

        node_id = msg.arbitration_id & 0x7F
        if node_id in self.network:
            self.network[node_id].on_message(msg)
