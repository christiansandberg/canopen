import collections
import logging
import can
from .node import Node


logger = logging.getLogger(__name__)


class Network(collections.Mapping):

    def __init__(self):
        self.bus = None
        self.listeners = [MessageDispatcher(self)]
        self.notifier = None
        self.nodes = []
        # NMT to all nodes
        #self.nmt = NmtNode(0)

    def connect(self, *args, **kwargs):
        # If bitrate has not been specified, try to find one node where bitrate
        # has been specified
        if "bitrate" not in kwargs:
            for node in self.nodes:
                if node.object_dictionary.bitrate:
                    kwargs["bitrate"] = node.object_dictionary.bitrate
                    break
        self.bus = can.interface.Bus(*args, **kwargs)
        logger.info("Connected to '%s'", self.bus.channel_info)
        self.notifier = can.Notifier(self.bus, self.listeners, 1)

    def disconnect(self):
        self.notifier.running.clear()

    def add_listener(self, listener):
        self.listeners.append(listener)

    def add_node(self, node, object_dictionary=None):
        if isinstance(node, int):
            node = Node(node, object_dictionary)
        node.network = self
        self.nodes.append(node)
        return node

    def send_message(self, can_id, data):
        assert self.bus, "Not connected to CAN bus"
        msg = can.Message(extended_id=False,
                          arbitration_id=can_id,
                          data=data)
        self.bus.send(msg)

    def put_message(self, can_id, data, timestamp):
        node_id = can_id & 0x7F
        for node in self.nodes:
            if node.id == node_id or node_id == 0:
                node.on_message(can_id, data, timestamp)
            for callback in node.callbacks:
                callback(can_id, data, timestamp)

    def __getitem__(self, node_id):
        for node in self.nodes:
            if node.id == node_id:
                return node

    def __iter__(self):
        return (node.id for node in self.nodes)

    def __len__(self):
        return len(self.nodes)


class MessageDispatcher(can.Listener):

    def __init__(self, network):
        self.network = network

    def on_message_received(self, msg):
        if msg.id_type or msg.is_error_frame or msg.is_remote_frame:
            return

        self.network.put_message(msg.arbitration_id, msg.data, msg.timestamp)
