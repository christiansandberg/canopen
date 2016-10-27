import time
import threading
import math
import collections
import logging
import binascii

from . import objectdictionary
from . import common


logger = logging.getLogger(__name__)


class PdoNode(object):
    """Represents a slave unit."""

    def __init__(self, parent):
        self.parent = parent
        self.rx = Maps(0x1400, 0x1600, self)
        self.tx = Maps(0x1800, 0x1A00, self)

    def on_message(self, can_id, data, timestamp):
        for pdo_map in self.tx.values():
            if pdo_map.cob_id == can_id:
                with pdo_map.receive_condition:
                    pdo_map.data = data
                    pdo_map.timestamp = timestamp
                    pdo_map.receive_condition.notify_all()

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
        """
        from canmatrix import canmatrix
        from canmatrix import formats

        db = canmatrix.CanMatrix()
        for pdo_maps in (self.rx, self.tx):
            for pdo_map in pdo_maps.values():
                if pdo_map.cob_id is None:
                    continue
                direction = "Tx" if pdo_map.cob_id & 0x80 else "Rx"
                map_id = pdo_map.cob_id >> 8
                name = "%sPDO%d_node%d" % (direction, map_id, self.parent.id)
                frame = canmatrix.Frame(name, Id=pdo_map.cob_id, extended=0)
                for var in pdo_map.map:
                    is_signed = var.od.data_type in objectdictionary.SIGNED_TYPES
                    is_float = var.od.data_type in objectdictionary.FLOAT_TYPES
                    min_value = var.od.min
                    max_value = var.od.max
                    if min_value is not None:
                        min_value *= var.od.factor
                    if max_value is not None:
                        max_value *= var.od.factor
                    signal = canmatrix.Signal(var.name.replace(".", "_"),
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


class Maps(collections.Mapping):
    """A collection of transmit or receive maps."""

    def __init__(self, com_offset, map_offset, pdo_node):
        self.pdo_node = pdo_node
        self.com_offset = com_offset
        self.maps = {}
        for map_no in range(32):
            self.maps[map_no + 1] = Message(
                pdo_node, com_offset + map_no, map_offset + map_no)

    def __getitem__(self, key):
        return self.maps[key]

    def __iter__(self):
        return iter(range(1, len(self) + 1))

    def __len__(self):
        for i in range(32):
            index = self.com_offset + i
            if index not in self.pdo_node.parent.object_dictionary:
                return i
        return 32


class Message(object):
    """One message which can have up to 8 bytes of variables mapped."""

    def __init__(self, pdo_node, com_index, map_index):
        self.pdo_node = pdo_node
        self.com_index = com_index
        self.map_index = map_index
        #: If this map is used or not
        self.enabled = False
        #: COB-ID for this PDO
        self.cob_id = None
        #: Transmission type (1-255)
        self.trans_type = None
        #: List of variables mapped to this PDO
        self.map = None
        #: Current message data
        self.data = bytearray()
        #: Timestamp of last received message
        self.timestamp = None
        #: Period of receive message transmission in seconds
        self.period = None
        self.transmit_thread = None
        self.receive_condition = threading.Condition()
        self.stop_event = threading.Event()

    def __getitem__(self, key):
        if isinstance(key, int):
            return self.map[key]
        else:
            for var in self.map:
                if var.name == key:
                    return var
        raise KeyError("%s not found in map", key)

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
        obj = self.pdo_node.parent.object_dictionary[index]
        if isinstance(obj, (objectdictionary.Record, objectdictionary.Array)):
            obj = obj[subindex]
        var = Variable(obj)
        var.msg = self
        return var

    def _update_data_size(self):
        self.data = bytearray(int(math.ceil(self._get_total_size() / 8.0)))

    def read(self):
        com_record = self.pdo_node.parent.sdo[self.com_index]
        map_record = self.pdo_node.parent.sdo[self.map_index]

        cob_id = com_record[1].raw
        self.cob_id = cob_id & 0x7FF
        logger.info("COB-ID is 0x%X", self.cob_id)
        self.enabled = cob_id & 0x80000000 == 0
        logger.info("PDO is %s", "enabled" if self.enabled else "disabled")
        self.trans_type = com_record[2].raw
        logger.info("Transmission type is %d", self.trans_type)

        self.map = []
        offset = 0
        for entry in map_record.values():
            if entry.od.subindex == 0:
                continue
            value = entry.raw
            index = value >> 16
            subindex = (value >> 8) & 0xFF
            size = value & 0xFF
            var = self._get_variable(index, subindex)
            assert size == len(var.od), "Size mismatch"
            var.offset = offset
            logger.info("Found %s (0x%X:%d) in PDO map",
                        var.name, index, subindex)
            self.map.append(var)
            offset += size
        self._update_data_size()

    def save(self):
        com_record = self.pdo_node.parent.sdo[self.com_index]
        map_record = self.pdo_node.parent.sdo[self.map_index]

        cob_id = com_record[1].raw
        if self.cob_id is None:
            self.cob_id = cob_id & 0x7FF
        if self.enabled is None:
            # Need to check if the PDO is enabled or not
            self.enabled = cob_id & 0x80000000 == 0
        logger.info("Setting COB-ID 0x%X and temporarily disabling PDO",
                    self.cob_id)
        com_record[1].raw = self.cob_id | 0x80000000
        if self.trans_type is not None:
            logger.info("Setting transmission type to %d", self.trans_type)
            com_record[2].raw = self.trans_type

        if self.map is not None:
            map_record[0].raw = len(self.map)
            subindex = 1
            for var in self.map:
                logger.info("Writing %s (0x%X:%d) to PDO map",
                            var.name, var.od.index, var.od.subindex)
                map_record[subindex].raw = (var.od.index << 16 |
                                            var.od.subindex << 8 |
                                            len(var.od))
                subindex += 1
            self._update_data_size()
        if self.enabled:
            logger.info("Enabling PDO")
            com_record[1].raw = self.cob_id

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
        self.pdo_node.parent.network.send_message(self.cob_id, self.data)

    def start(self, period=None):
        """Start periodic transmission of message in a background thread.

        :param float period: Transmission period in seconds
        """
        if period is not None:
            self.period = period

        if not self.period:
            raise ValueError("A valid transmission period has not been given")

        if not self.transmit_thread or not self.transmit_thread.is_alive():
            self.stop_event.clear()
            self.transmit_thread = threading.Thread(
                target=self._periodic_transmit)
            self.transmit_thread.daemon = True
            self.transmit_thread.start()

    def stop(self):
        """Stop transmission."""
        self.stop_event.set()
        self.transmit_thread = None

    def wait_for_reception(self, timeout=10):
        """Wait for the next transmit PDO.

        :param float timeout: Max time to wait in seconds.
        :return: Timestamp of message received or None if timeout.
        :rtype: float
        """
        with self.receive_condition:
            self.timestamp = None
            self.receive_condition.wait(timeout)
        return self.timestamp

    def _periodic_transmit(self):
        while not self.stop_event.is_set():
            start = time.time()
            self.transmit()
            time_left = self.period - (time.time() - start)
            time.sleep(max(time_left, 0.0))


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
        return self.msg.data[byte_offset:byte_offset + len(self.od) // 8]

    def set_data(self, data):
        byte_offset = self.offset // 8
        logger.debug("Updating %s to %s in message 0x%X",
            self.name, binascii.hexlify(data), self.msg.cob_id)
        self.msg.data[byte_offset:byte_offset + len(data)] = data
