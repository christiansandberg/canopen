import sys
import time
import threading
import math
import collections
import logging
import binascii

from .network import CanError
from . import objectdictionary
from . import common


PDO_NOT_VALID = 1 << 31
RTR_NOT_ALLOWED = 1 << 30


if hasattr(time, "perf_counter"):
    # Choose time.perf_counter if available
    timer = time.perf_counter
elif sys.platform == "win32":
    # On Windows, the best timer is time.clock
    timer = time.clock
else:
    # On most other platforms the best timer is time.time
    timer = time.time


logger = logging.getLogger(__name__)


class PdoNode(object):
    """Represents a slave unit."""

    def __init__(self, node):
        self.network = None
        self.node = node
        self.rx = Maps(0x1400, 0x1600, self)
        self.tx = Maps(0x1800, 0x1A00, self)

    def get_by_name(self, name):
        """Finds a map entry matching ``name``.

        :param str name: Name in the format of Group.Name.
        :return: The matching variable object.
        :rtype: canopen.pdo.Variable
        :raises ValueError: When name is not found in map
        """
        for pdo_maps in (self.rx, self.tx):
            for pdo_map in pdo_maps.values():
                for var in pdo_map.map:
                    if var.name == name:
                        return var
        raise ValueError("%s was not found in any map" % name)

    def read(self):
        """Read PDO configuration from node using SDO."""
        for pdo_maps in (self.rx, self.tx):
            for pdo_map in pdo_maps.values():
                pdo_map.read()

    def save(self):
        """Save PDO configuration to node using SDO."""
        for pdo_maps in (self.rx, self.tx):
            for pdo_map in pdo_maps.values():
                pdo_map.save()

    def export(self, filename):
        """Export current configuration to a database file.

        :param str filename:
            Filename to save to (e.g. DBC, DBF, ARXML, KCD etc)

        :return: The CanMatrix object created
        :rtype: canmatrix.canmatrix.CanMatrix
        """
        from canmatrix import canmatrix
        from canmatrix import formats

        db = canmatrix.CanMatrix()
        for pdo_maps in (self.rx, self.tx):
            for pdo_map in pdo_maps.values():
                if pdo_map.cob_id is None:
                    continue
                frame = canmatrix.Frame(pdo_map.name,
                                        Id=pdo_map.cob_id,
                                        extended=0)
                for var in pdo_map.map:
                    is_signed = var.od.data_type in objectdictionary.SIGNED_TYPES
                    is_float = var.od.data_type in objectdictionary.FLOAT_TYPES
                    min_value = var.od.min
                    max_value = var.od.max
                    if min_value is not None:
                        min_value *= var.od.factor
                    if max_value is not None:
                        max_value *= var.od.factor
                    name = var.name
                    name = name.replace(" ", "_")
                    name = name.replace(".", "_")
                    signal = canmatrix.Signal(name,
                                              startBit=var.offset,
                                              signalSize=len(var.od),
                                              is_signed=is_signed,
                                              is_float=is_float,
                                              factor=var.od.factor,
                                              min=min_value,
                                              max=max_value,
                                              unit=var.od.unit)
                    for value, desc in var.od.value_descriptions.items():
                        signal.addValues(value, desc)
                    frame.addSignal(signal)
                frame.calcDLC()
                db.frames.addFrame(frame)
        formats.dumpp({"": db}, filename)
        return db

    def stop(self):
        """Stop transmission of all Rx PDOs."""
        for pdo_map in self.rx.values():
            pdo_map.stop()

class Maps(collections.Mapping):
    """A collection of transmit or receive maps."""

    def __init__(self, com_offset, map_offset, pdo_node):
        self.maps = {}
        for map_no in range(32):
            if com_offset + map_no in pdo_node.node.object_dictionary:
                self.maps[map_no + 1] = Map(
                    pdo_node,
                    pdo_node.node.sdo[com_offset + map_no],
                    pdo_node.node.sdo[map_offset + map_no])

    def __getitem__(self, key):
        return self.maps[key]

    def __iter__(self):
        return iter(self.maps)

    def __len__(self):
        return len(self.maps)


class Map(object):
    """One message which can have up to 8 bytes of variables mapped."""

    def __init__(self, pdo_node, com_record, map_array):
        self.pdo_node = pdo_node
        self.com_record = com_record
        self.map_array = map_array
        #: If this map is valid
        self.enabled = False
        #: COB-ID for this PDO
        self.cob_id = None
        #: Is the remote transmit request (RTR) allowed for this PDO
        self.rtr_allowed = True
        #: Transmission type (0-255)
        self.trans_type = None
        #: List of variables mapped to this PDO
        self.map = None
        #: Current message data
        self.data = bytearray()
        #: Timestamp of last received message
        self.timestamp = 0
        #: Period of receive message transmission in seconds
        self.period = None
        self.callbacks = []
        self.transmit_thread = None
        self.receive_condition = threading.Condition()
        self.stop_event = threading.Event()
        self.is_received = False

    def __getitem__(self, key):
        if isinstance(key, int):
            return self.map[key]
        else:
            valid_values = []
            for var in self.map:
                valid_values.append(var.name)
                if var.name == key:
                    return var
        raise KeyError("%s not found in map. Valid entries are %s" % (
            key, ", ".join(valid_values)))

    def __iter__(self):
        return iter(self.map)

    def __len__(self):
        return len(self.map)

    def _get_total_size(self):
        size = 0
        for var in self.map:
            size += len(var.od)
        return size

    def _get_variable(self, index, subindex):
        obj = self.pdo_node.node.object_dictionary[index]
        if isinstance(obj, (objectdictionary.Record, objectdictionary.Array)):
            obj = obj[subindex]
        var = Variable(obj)
        var.msg = self
        return var

    def _update_data_size(self):
        self.data = bytearray(int(math.ceil(self._get_total_size() / 8.0)))

    @property
    def name(self):
        """A descriptive name of the PDO.

        Examples:
         * TxPDO1_node4
         * RxPDO4_node1
        """
        direction = "Tx" if self.cob_id & 0x80 else "Rx"
        map_id = self.cob_id >> 8
        if direction == "Rx":
            map_id -= 1
        node_id = self.cob_id & 0x7F
        return "%sPDO%d_node%d" % (direction, map_id, node_id)

    def on_message(self, can_id, data, timestamp):
        is_transmitting = self.transmit_thread and self.transmit_thread.is_alive()
        if can_id == self.cob_id and not is_transmitting:
            with self.receive_condition:
                self.is_received = True
                self.data = data
                self.period = timestamp - self.timestamp
                self.timestamp = timestamp
                self.receive_condition.notify_all()
                for callback in self.callbacks:
                    callback(self)

    def add_callback(self, callback):
        """Add a callback which will be called on receive.

        :param callback:
            The function to call which must take one argument of a
            :class:`~canopen.pdo.Map`.
        """
        self.callbacks.append(callback)

    def read(self):
        """Read PDO configuration for this map using SDO."""
        cob_id = self.com_record[1].raw
        self.cob_id = cob_id & 0x7FF
        logger.info("COB-ID is 0x%X", self.cob_id)
        self.enabled = cob_id & PDO_NOT_VALID == 0
        logger.info("PDO is %s", "enabled" if self.enabled else "disabled")
        self.rtr_allowed = cob_id & RTR_NOT_ALLOWED == 0
        logger.info("RTR is %s", "allowed" if self.rtr_allowed else "not allowed")
        self.trans_type = self.com_record[2].raw
        logger.info("Transmission type is %d", self.trans_type)

        self.map = []
        offset = 0
        for entry in self.map_array.values():
            if entry.od.subindex == 0:
                continue
            value = entry.raw
            index = value >> 16
            subindex = (value >> 8) & 0xFF
            size = value & 0xFF
            if size == 0:
                continue
            var = self._get_variable(index, subindex)
            assert size == len(var.od), "Size mismatch"
            var.offset = offset
            logger.info("Found %s (0x%X:%d) in PDO map",
                        var.name, index, subindex)
            self.map.append(var)
            offset += size
        self._update_data_size()

        if self.enabled:
            self.pdo_node.network.subscribe(self.cob_id, self.on_message)

    def save(self):
        """Save PDO configuration for this map using SDO."""
        cob_id = self.com_record[1].raw
        if self.cob_id is None:
            self.cob_id = cob_id & 0x7FF
        if self.enabled is None:
            # Need to check if the PDO is enabled or not
            self.enabled = cob_id & PDO_NOT_VALID == 0
        logger.info("Setting COB-ID 0x%X and temporarily disabling PDO",
                    self.cob_id)
        self.com_record[1].raw = self.cob_id | PDO_NOT_VALID
        if self.trans_type is not None:
            logger.info("Setting transmission type to %d", self.trans_type)
            self.com_record[2].raw = self.trans_type

        if self.map is not None:
            self.map_array[0].raw = 0
            subindex = 1
            for var in self.map:
                logger.info("Writing %s (0x%X:%d) to PDO map",
                            var.name, var.od.index, var.od.subindex)
                self.map_array[subindex].raw = (var.od.index << 16 |
                                                var.od.subindex << 8 |
                                                len(var.od))
                subindex += 1
            self.map_array[0].raw = len(self.map)
            self._update_data_size()

        if self.enabled:
            logger.info("Enabling PDO")
            self.com_record[1].raw = self.cob_id
            self.pdo_node.network.subscribe(self.cob_id, self.on_message)

    def clear(self):
        """Clear all variables from this map."""
        self.map = []

    def add_variable(self, index, subindex=0):
        """Add a variable from object dictionary as the next entry.

        :param index: Index of variable as name or number
        :param subindex: Sub-index of variable as name or number
        :type index: :class:`str` or :class:`int`
        :type subindex: :class:`str` or :class:`int`
        :return: Variable that was added
        :rtype: canopen.pdo.Variable
        """
        if self.map is None:
            self.map = []
        var = self._get_variable(index, subindex)
        var.offset = self._get_total_size()
        logger.info("Adding %s (0x%X:%d) to PDO map",
                    var.name, var.od.index, var.od.subindex)
        self.map.append(var)
        assert self._get_total_size() <= 64, "Max size of PDO exceeded"
        return var

    def transmit(self):
        """Transmit the message once."""
        self.pdo_node.network.send_message(self.cob_id, self.data)

    def start(self, period=None):
        """Start periodic transmission of message in a background thread.

        :param float period: Transmission period in seconds
        """
        if period is not None:
            self.period = period

        if not self.period:
            raise ValueError("A valid transmission period has not been given")
        logger.info("Starting %s with a period of %s seconds", self.name, self.period)

        if not self.transmit_thread or not self.transmit_thread.is_alive():
            self.stop_event.clear()
            self.transmit_thread = threading.Thread(
                name=self.name,
                target=self._periodic_transmit)
            self.transmit_thread.daemon = True
            self.transmit_thread.start()

    def stop(self):
        """Stop transmission."""
        self.stop_event.set()
        self.transmit_thread = None

    def remote_request(self):
        """Send a remote request for the transmit PDO.
        Silently ignore if not allowed.
        """
        if self.enabled and self.rtr_allowed:
            self.pdo_node.network.send_message(self.cob_id, None, remote=True)

    def wait_for_reception(self, timeout=10):
        """Wait for the next transmit PDO.

        :param float timeout: Max time to wait in seconds.
        :return: Timestamp of message received or None if timeout.
        :rtype: float
        """
        with self.receive_condition:
            self.is_received = False
            self.receive_condition.wait(timeout)
        return self.timestamp if self.is_received else None

    def _periodic_transmit(self):
        while not self.stop_event.is_set():
            start = timer()
            try:
                self.transmit()
            except CanError as error:
                print(str(error))
            time_left = self.period - (timer() - start)
            if time_left > 0:
                time.sleep(time_left)


class Variable(common.Variable):
    """One object dictionary variable mapped to a PDO."""

    def __init__(self, od):
        self.msg = None
        #: Location of variable in the message in bits
        self.offset = None
        self.name = od.name
        if isinstance(od.parent, (objectdictionary.Record,
                                  objectdictionary.Array)):
            self.name = od.parent.name + "." + self.name
        common.Variable.__init__(self, od)

    def get_data(self):
        byte_offset = self.offset // 8
        return bytes(self.msg.data[byte_offset:byte_offset + len(self.od) // 8])

    def set_data(self, data):
        byte_offset = self.offset // 8
        logger.debug("Updating %s to %s in message 0x%X",
                     self.name, binascii.hexlify(data), self.msg.cob_id)
        self.msg.data[byte_offset:byte_offset + len(data)] = data
