import collections
import threading
import logging
import can
from .node import Node
from .nmt import NmtNode
try:
    import queue as queue
except ImportError:
    import Queue as queue


logger = logging.getLogger(__name__)


class Network(collections.Mapping):

    def __init__(self):
        self.bus = None
        self.dispatcher = MessageDispatcher(self)
        self.notifier = None
        self.nodes = {}
        self.stop_event = threading.Event()
        self.tx_queue = queue.Queue()
        self.send_thread = threading.Thread(target=self._send_to_can)
        self.send_thread.daemon = True
        # NMT to all nodes
        self.nmt = NmtNode(0)

    def connect(self, *args, **kwargs):
        self.bus = can.interface.Bus(*args, **kwargs)
        logger.info("Connected to '%s'", self.bus.channel_info)
        self.notifier = can.Notifier(self.bus, [self.dispatcher], 1)
        self.send_thread.start()

    def disconnect(self):
        self.notifier.running.clear()
        self.stop_event.set()
        self.send_thread.join(2)

    def _send_to_can(self):
        while not self.stop_event.is_set():
            can_id, data = self.get_message()
            if can_id is not None:
                msg = can.Message(extended_id=False,
                                  arbitration_id=can_id,
                                  data=data)
                try:
                    self.bus.send(msg)
                except can.CanError as e:
                    logger.error(e)
        self.bus.shutdown()

    def add_node(self, node, object_dictionary=None):
        if isinstance(node, int):
            node = Node(node, object_dictionary)
        node.network = self
        self.nodes[node.id] = node
        return node

    def send_message(self, can_id, data):
        self.tx_queue.put((can_id, data))

    def get_message(self, timeout=1):
        try:
            return self.tx_queue.get(block=True, timeout=timeout)
        except queue.Empty:
            return (None, None)

    def put_message(self, can_id, data):
        node_id = can_id & 0x7F
        if node_id == 0:
            # Broadcast?
            for node in self.nodes.values():
                node.on_message(can_id, data)
        elif node_id in self.nodes:
            self.nodes[node_id].on_message(can_id, data)

    def __getitem__(self, node_id):
        return self.nodes[node_id]

    def __iter__(self):
        return iter(self.nodes)

    def __len__(self):
        return len(self.nodes)

    def __contains__(self, node_id):
        return node_id in self.nodes


class MessageDispatcher(can.Listener):

    def __init__(self, network):
        self.network = network

    def on_message_received(self, msg):
        if msg.id_type or msg.is_error_frame or msg.is_remote_frame:
            return

        self.network.put_message(msg.arbitration_id, msg.data)
