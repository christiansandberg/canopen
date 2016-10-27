import collections
import logging
import threading

try:
    import can
    from can import Listener
except ImportError:
    # Do not fail if python-can is not installed
    can = None
    Listener = object

from .node import Node
from .sync import SyncProducer


logger = logging.getLogger(__name__)


class Network(collections.Mapping):
    """Representation of one CAN bus containing one or more nodes."""

    def __init__(self):
        #: A python-can :class:`can.BusABC` instance which is set after
        #: :meth:`canopen.Network.connect` is called
        self.bus = None
        self.listeners = [MessageDispatcher(self)]
        self.notifier = None
        self.nodes = []
        self.send_lock = threading.Lock()
        #: The SYNC producer
        self.sync = SyncProducer(self)
        # NMT to all nodes
        #self.nmt = NmtNode(0)

    def connect(self, *args, **kwargs):
        """Connect to CAN bus using python-can.

        Arguments are passed directly to :class:`can.BusABC`. Typically these
        may include:

        :param channel:
            Backend specific channel for the CAN interface.
        :param str bustype:
            Name of the interface, e.g. 'kvaser', 'socketcan', 'pcan'...
        :param int bitrate:
            Bitrate in bit/s.

        :raises can.CanError:
            When connection fails.
        """
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
        """Disconnect from the CAN bus.
        
        Must be overridden in a subclass if a custom interface is used.
        """
        self.notifier.stop()
        self.bus.shutdown()

    def add_listener(self, listener):
        """Add any :class:`can.Listener` object to the network.""" 
        self.listeners.append(listener)

    def add_node(self, node, object_dictionary=None):
        """Add a node to the network.

        :param node:
            Can be either an integer representing the node ID or a
            :class:`canopen.Node` object.
        :param object_dictionary:
            Can be either a string for specifying the path to an
            Object Dictionary file or a
            :class:`canopen.ObjectDictionary` object.

        :return:
            The Node object that was added.
        :rtype: canopen.Node
        """
        if isinstance(node, int):
            node = Node(node, object_dictionary)
        node.network = self
        self.nodes.append(node)
        return node

    def send_message(self, can_id, data):
        """Send a raw CAN message to the network.

        This method may be overridden in a subclass if you need to integrate
        this library with a custom backend.
        It is safe to call this from multiple threads.

        :param int can_id:
            CAN-ID of the message (always 11-bit)
        :param data:
            Data to be transmitted (anything that can be converted to bytes)

        :raises can.CanError:
            When the message fails to be transmitted
        """
        assert self.bus, "Not connected to CAN bus"
        msg = can.Message(extended_id=False,
                          arbitration_id=can_id,
                          data=data)
        with self.send_lock:
            self.bus.send(msg)

    def put_message(self, can_id, data, timestamp):
        """Feed incoming message to this library.

        If a custom interface is used, this function must be called for each
        11-bit standard message read from the CAN bus.

        :param int can_id:
            CAN-ID of the message (always 11-bit)
        :param bytes data:
            Data part of the message (0 - 8 bytes)
        :param float timestamp:
            Timestamp of the message, preferably as a Unix timestamp
        """
        node_id = can_id & 0x7F
        for node in self.nodes:
            if node.id == node_id or node_id == 0:
                node.on_message(can_id, data, timestamp)
            for callback in node.message_callbacks:
                callback(can_id, data, timestamp)

    def __getitem__(self, node_id):
        for node in self.nodes:
            if node.id == node_id:
                return node

    def __iter__(self):
        return (node.id for node in self.nodes)

    def __len__(self):
        return len(self.nodes)


class MessageDispatcher(Listener):
    """Listens for messages on CAN bus and feeds them to a Network instance."""

    def __init__(self, network):
        self.network = network

    def on_message_received(self, msg):
        if msg.id_type or msg.is_error_frame or msg.is_remote_frame:
            return

        self.network.put_message(msg.arbitration_id, msg.data, msg.timestamp)
