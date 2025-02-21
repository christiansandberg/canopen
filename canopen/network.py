from __future__ import annotations

import asyncio
import logging
import threading
from collections.abc import MutableMapping
from typing import Callable, Dict, Final, Iterator, List, Optional, Union

import can
from can import Listener

from canopen.async_guard import set_async_sentinel
from canopen.lss import LssMaster
from canopen.nmt import NmtMaster
from canopen.node import LocalNode, RemoteNode
from canopen.objectdictionary import ObjectDictionary
from canopen.objectdictionary.eds import import_from_node
from canopen.sync import SyncProducer
from canopen.timestamp import TimeProducer


logger = logging.getLogger(__name__)

Callback = Callable[[int, bytearray, float], None]


class Network(MutableMapping):
    """Representation of one CAN bus containing one or more nodes."""

    NOTIFIER_CYCLE: float = 1.0  #: Maximum waiting time for one notifier iteration.
    NOTIFIER_SHUTDOWN_TIMEOUT: float = 5.0  #: Maximum waiting time to stop notifiers.

    def __init__(self, bus: Optional[can.BusABC] = None, notifier: Optional[can.Notifier] = None,
                 loop: Optional[asyncio.AbstractEventLoop] = None):
        """
        :param can.BusABC bus:
            A python-can bus instance to re-use.
        """
        #: A python-can :class:`can.BusABC` instance which is set after
        #: :meth:`canopen.Network.connect` is called
        self.bus: Optional[BusABC] = bus
        self.loop: Optional[asyncio.AbstractEventLoop] = loop
        #: A :class:`~canopen.network.NodeScanner` for detecting nodes
        self.scanner = NodeScanner(self)
        #: List of :class:`can.Listener` objects.
        #: Includes at least MessageListener.
        self.listeners = [MessageListener(self)]
        self.notifier: Optional[can.Notifier] = notifier
        self.nodes: Dict[int, Union[RemoteNode, LocalNode]] = {}
        self.subscribers: Dict[int, List[Callback]] = {}
        self.send_lock = threading.Lock()
        self.sync = SyncProducer(self)
        self.time = TimeProducer(self)
        self.nmt = NmtMaster(0)
        self.nmt.network = self

        self.lss = LssMaster()
        self.lss.network = self

        # Register this function as the means to check if canopen is run in
        # async mode. This enables the @ensure_not_async() decorator to
        # work. See async_guard.py
        set_async_sentinel(self.is_async)

        if self.is_async():
            self.subscribe(self.lss.LSS_RX_COBID, self.lss.aon_message_received)
        else:
            self.subscribe(self.lss.LSS_RX_COBID, self.lss.on_message_received)

    def subscribe(self, can_id: int, callback: Callback) -> None:
        """Listen for messages with a specific CAN ID.

        :param can_id:
            The CAN ID to listen for.
        :param callback:
            Function to call when message is received.
        """
        self.subscribers.setdefault(can_id, list())
        if callback not in self.subscribers[can_id]:
            self.subscribers[can_id].append(callback)

    def unsubscribe(self, can_id, callback=None) -> None:
        """Stop listening for message.

        :param int can_id:
            The CAN ID from which to unsubscribe.
        :param callback:
            If given, remove only this callback.  Otherwise all callbacks for
            the CAN ID.
        """
        if callback is None:
            del self.subscribers[can_id]
        else:
            self.subscribers[can_id].remove(callback)

    def connect(self, *args, **kwargs) -> Network:
        """Connect to CAN bus using python-can.

        Arguments are passed directly to :class:`can.BusABC`. Typically these
        may include:

        :param channel:
            Backend specific channel for the CAN interface.
        :param str interface:
            Name of the interface. See
            `python-can manual <https://python-can.readthedocs.io/en/stable/configuration.html#interface-names>`__
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
        if self.bus is None:
            self.bus = can.Bus(*args, **kwargs)
        logger.info("Connected to '%s'", self.bus.channel_info)
        if self.notifier is None:
            self.notifier = can.Notifier(self.bus, [], self.NOTIFIER_CYCLE, loop=self.loop)
        for listener in self.listeners:
            self.notifier.add_listener(listener)
        return self

    def disconnect(self) -> None:
        """Disconnect from the CAN bus.

        Must be overridden in a subclass if a custom interface is used.
        """
        for node in self.nodes.values():
            if hasattr(node, "pdo"):
                node.pdo.stop()
        if self.notifier is not None:
            self.notifier.stop(self.NOTIFIER_SHUTDOWN_TIMEOUT)
        if self.bus is not None:
            self.bus.shutdown()
        self.bus = None
        self.check()

    def __enter__(self):
        return self

    def __exit__(self, type, value, traceback):
        self.disconnect()

    # FIXME: Implement async "aadd_node"

    def add_node(
        self,
        node: Union[int, RemoteNode, LocalNode],
        object_dictionary: Union[str, ObjectDictionary, None] = None,
        upload_eds: bool = False,
    ) -> RemoteNode:
        """Add a remote node to the network.

        :param node:
            Can be either an integer representing the node ID, a
            :class:`canopen.RemoteNode` or :class:`canopen.LocalNode` object.
        :param object_dictionary:
            Can be either a string for specifying the path to an
            Object Dictionary file or a
            :class:`canopen.ObjectDictionary` object.
        :param upload_eds:
            Set ``True`` if EDS file should be uploaded from 0x1021.

        :return:
            The Node object that was added.
        """
        if isinstance(node, int):
            if upload_eds:
                logger.info("Trying to read EDS from node %d", node)
                object_dictionary = import_from_node(node, self)
            node = RemoteNode(node, object_dictionary)
        self[node.id] = node
        return node

    def create_node(
        self,
        node: int,
        object_dictionary: Union[str, ObjectDictionary, None] = None,
    ) -> LocalNode:
        """Create a local node in the network.

        :param node:
            An integer representing the node ID.
        :param object_dictionary:
            Can be either a string for specifying the path to an
            Object Dictionary file or a
            :class:`canopen.ObjectDictionary` object.

        :return:
            The Node object that was added.
        """
        if isinstance(node, int):
            node = LocalNode(node, object_dictionary)
        self[node.id] = node
        return node

    def send_message(self, can_id: int, data: bytes, remote: bool = False) -> None:
        """Send a raw CAN message to the network.

        This method may be overridden in a subclass if you need to integrate
        this library with a custom backend.
        It is safe to call this from multiple threads.

        :param int can_id:
            CAN-ID of the message
        :param data:
            Data to be transmitted (anything that can be converted to bytes)
        :param bool remote:
            Set to True to send remote frame

        :raises can.CanError:
            When the message fails to be transmitted
        """
        if not self.bus:
            raise RuntimeError("Not connected to CAN bus")
        msg = can.Message(is_extended_id=can_id > 0x7FF,
                          arbitration_id=can_id,
                          data=data,
                          is_remote_frame=remote)
        # NOTE: Blocking lock. This is probably ok for async, because async
        #       only use one thread.
        with self.send_lock:
            self.bus.send(msg)
        self.check()

    def send_periodic(
        self, can_id: int, data: bytes, period: float, remote: bool = False
    ) -> PeriodicMessageTask:
        """Start sending a message periodically.

        :param can_id:
            CAN-ID of the message
        :param data:
            Data to be transmitted (anything that can be converted to bytes)
        :param period:
            Seconds between each message
        :param remote:
            indicates if the message frame is a remote request to the slave node

        :return:
            An task object with a ``.stop()`` method to stop the transmission
        """
        return PeriodicMessageTask(can_id, data, period, self.bus, remote)

    def notify(self, can_id: int, data: bytearray, timestamp: float) -> None:
        """Feed incoming message to this library.

        If a custom interface is used, this function must be called for each
        message read from the CAN bus.

        :param can_id:
            CAN-ID of the message
        :param data:
            Data part of the message (0 - 8 bytes)
        :param timestamp:
            Timestamp of the message, preferably as a Unix timestamp
        """
        # NOTE: Callback. Called from another thread unless async
        callbacks = self.subscribers.get(can_id)
        if callbacks is not None:
            for callback in callbacks:
                res = callback(can_id, data, timestamp)
                if res is not None and self.loop is not None and asyncio.iscoroutine(res):
                    self.loop.create_task(res)
        self.scanner.on_message_received(can_id)

    def check(self) -> None:
        """Check that no fatal error has occurred in the receiving thread.

        If an exception caused the thread to terminate, that exception will be
        raised.
        """
        if self.notifier is not None:
            exc = self.notifier.exception
            if exc is not None:
                logger.error("An error has caused receiving of messages to stop")
                raise exc

    def is_async(self) -> bool:
        """Check if canopen has been connected with async"""
        return self.loop is not None

    def __getitem__(self, node_id: int) -> Union[RemoteNode, LocalNode]:
        return self.nodes[node_id]

    def __setitem__(self, node_id: int, node: Union[RemoteNode, LocalNode]):
        assert node_id == node.id
        if node_id in self.nodes:
            # Remove old callbacks
            self.nodes[node_id].remove_network()
        self.nodes[node_id] = node
        node.associate_network(self)

    def __delitem__(self, node_id: int):
        self.nodes[node_id].remove_network()
        del self.nodes[node_id]

    def __iter__(self) -> Iterator[int]:
        return iter(self.nodes)

    def __len__(self) -> int:
        return len(self.nodes)


class _UninitializedNetwork(Network):
    """Empty network implementation as a placeholder before actual initialization."""

    def __init__(self, bus: Optional[can.BusABC] = None):
        """Do not initialize attributes, by skipping the parent constructor."""

    def __getattribute__(self, name):
        raise RuntimeError("No actual Network object was assigned, "
                           "try associating to a real network first.")


#: Singleton instance
_UNINITIALIZED_NETWORK: Final[Network] = _UninitializedNetwork()


class PeriodicMessageTask:
    """
    Task object to transmit a message periodically using python-can's
    CyclicSendTask
    """

    def __init__(
        self,
        can_id: int,
        data: bytes,
        period: float,
        bus,
        remote: bool = False,
    ):
        """
        :param can_id:
            CAN-ID of the message
        :param data:
            Data to be transmitted (anything that can be converted to bytes)
        :param period:
            Seconds between each message
        :param can.BusABC bus:
            python-can bus to use for transmission
        """
        self.bus = bus
        self.period = period
        self.msg = can.Message(is_extended_id=can_id > 0x7FF,
                               arbitration_id=can_id,
                               data=data, is_remote_frame=remote)
        self._start()

    def _start(self):
        self._task = self.bus.send_periodic(self.msg, self.period)

    def stop(self):
        """Stop transmission"""
        self._task.stop()

    def update(self, data: bytes) -> None:
        """Update data of message

        :param data:
            New data to transmit
        """
        # NOTE: Callback. Called from another thread unless async
        new_data = bytearray(data)
        old_data = self.msg.data
        self.msg.data = new_data
        if hasattr(self._task, "modify_data"):
            self._task.modify_data(self.msg)
        elif new_data != old_data:
            # Stop and start (will mess up period unfortunately)
            self._task.stop()
            self._start()


class MessageListener(Listener):
    """Listens for messages on CAN bus and feeds them to a Network instance.

    :param network:
        The network to notify on new messages.
    """

    def __init__(self, network: Network):
        self.network = network

    def on_message_received(self, msg):
        # NOTE: Callback. Called from another thread unless async
        if msg.is_error_frame or msg.is_remote_frame:
            return

        try:
            self.network.notify(msg.arbitration_id, msg.data, msg.timestamp)
        except Exception as e:
            # Exceptions in any callbaks should not affect CAN processing
            logger.error(str(e))

    def stop(self) -> None:
        """Override abstract base method to release any resources."""


class NodeScanner:
    """Observes which nodes are present on the bus.

    Listens for the following messages:
     - Heartbeat (0x700)
     - SDO response (0x580)
     - TxPDO (0x180, 0x280, 0x380, 0x480)
     - EMCY (0x80)

    :param canopen.Network network:
        The network to use when doing active searching.
    """

    SERVICES = (0x700, 0x580, 0x180, 0x280, 0x380, 0x480, 0x80)

    def __init__(self, network: Optional[Network] = None):
        self.network = network
        #: A :class:`list` of nodes discovered
        self.nodes: List[int] = []

    def on_message_received(self, can_id: int):
        # NOTE: Callback. Called from another thread unless async
        service = can_id & 0x780
        node_id = can_id & 0x7F
        if node_id not in self.nodes and node_id != 0 and service in self.SERVICES:
            # NOTE: In the current CPython implementation append on lists are
            #       atomic which makes this thread-safe. However, other py
            #       interpreters might not. It should be considered if a better
            #       mechanism is needed to protect against race.
            self.nodes.append(node_id)

    def reset(self):
        """Clear list of found nodes."""
        self.nodes = []

    def search(self, limit: int = 127) -> None:
        """Search for nodes by sending SDO requests to all node IDs."""
        if self.network is None:
            raise RuntimeError("A Network is required to do active scanning")
        # SDO upload request, parameter 0x1000:0x00
        sdo_req = b"\x40\x00\x10\x00\x00\x00\x00\x00"
        for node_id in range(1, limit + 1):
            self.network.send_message(0x600 + node_id, sdo_req)
