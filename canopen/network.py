import collections
import logging
import threading

try:
    import can
    from can import Listener
    from can import CanError
except ImportError:
    # Do not fail if python-can is not installed
    can = None
    Listener = object
    CanError = Exception

from .node import Node
from .sync import SyncProducer
from .nmt import NmtMaster


logger = logging.getLogger(__name__)


class Network(collections.MutableMapping):
    """Representation of one CAN bus containing one or more nodes."""

    def __init__(self):
        #: A python-can :class:`can.BusABC` instance which is set after
        #: :meth:`canopen.Network.connect` is called
        self.bus = None
        #: List of :class:`can.Listener` objects.
        #: Includes at least MessageListener.
        self.listeners = [MessageListener(self)]
        self.notifier = None
        self.nodes = {}
        self.subscribers = {}
        self.send_lock = threading.Lock()
        self.sync = SyncProducer(self)
        self.nmt = NmtMaster(0)
        self.nmt.network = self

    def subscribe(self, can_id, callback):
        """Listen for messages with a specific CAN ID.

        :param int can_id:
            The CAN ID to listen for.
        :param callback:
            Function to call when message is received.
        """
        self.subscribers.setdefault(can_id, [])
        if callback not in self.subscribers[can_id]:
            self.subscribers[can_id].append(callback)

    def unsubscribe(self, can_id, callback):
        """Stop listening for message."""
        self.subscribers[can_id].remove(callback)

    def connect(self, *args, **kwargs):
        """Connect to CAN bus using python-can.

        Arguments are passed directly to :class:`can.BusABC`. Typically these
        may include:

        :param channel:
            Backend specific channel for the CAN interface.
        :param str bustype:
            Name of the interface. See
            `python-can manual <https://python-can.readthedocs.io/en/latest/configuration.html#interface-names>`__
            for full list of supported interfaces.
        :param int bitrate:
            Bitrate in bit/s.

        :raises can.CanError:
            When connection fails.
        """
        # If bitrate has not been specified, try to find one node where bitrate
        # has been specified
        if "bitrate" not in kwargs:
            for node in self.nodes.values():
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
        self.bus = None

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
        self.nodes[node.id] = node
        node.associate_network(self)
        return node

    def send_message(self, can_id, data, remote=False):
        """Send a raw CAN message to the network.

        This method may be overridden in a subclass if you need to integrate
        this library with a custom backend.
        It is safe to call this from multiple threads.

        :param int can_id:
            CAN-ID of the message (always 11-bit)
        :param data:
            Data to be transmitted (anything that can be converted to bytes)
        :param bool remote:
            Set to True to send remote frame

        :raises can.CanError:
            When the message fails to be transmitted
        """
        assert self.bus, "Not connected to CAN bus"
        msg = can.Message(extended_id=False,
                          arbitration_id=can_id,
                          data=data,
                          is_remote_frame=remote)
        with self.send_lock:
            self.bus.send(msg)

    def notify(self, can_id, data, timestamp):
        """Feed incoming message to this library.

        If a custom interface is used, this function must be called for each
        11-bit standard message read from the CAN bus.

        :param int can_id:
            CAN-ID of the message (always 11-bit)
        :param bytearray data:
            Data part of the message (0 - 8 bytes)
        :param float timestamp:
            Timestamp of the message, preferably as a Unix timestamp
        """
        for callback in self.subscribers.get(can_id, []):
            callback(can_id, data, timestamp)

    def __getitem__(self, node_id):
        return self.nodes[node_id]

    def __setitem__(self, node_id, node):
        assert node_id == node.id
        self.nodes[node_id] = node
        node.associate_network(self)

    def __delitem__(self, node_id):
        self.nodes[node_id].remove_network()
        del self.nodes[node_id]

    def __iter__(self):
        return iter(self.nodes)

    def __len__(self):
        return len(self.nodes)


class MessageListener(Listener):
    """Listens for messages on CAN bus and feeds them to a Network instance."""

    def __init__(self, network):
        self.network = network

    def on_message_received(self, msg):
        if msg.is_error_frame or msg.is_remote_frame:
            return

        self.network.notify(msg.arbitration_id, msg.data, msg.timestamp)
