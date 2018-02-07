import threading
import math
import collections
import logging
import binascii

from .sdo import SdoAbortedError
from . import objectdictionary
from . import variable


PDO_NOT_VALID = 1 << 31
RTR_NOT_ALLOWED = 1 << 30


logger = logging.getLogger(__name__)

# TODO: Load the PDOs as configured in the EDS file
# TODO: Handle the mapping configuration
# TODO: Support the PDO trigger types
# TODO: Depending on the trigger a write to a variable needs to trigger a PDO
#       message send
# TODO: PDOs support data mapping on the bit level (e.g. 10 bits)
# TODO: Depending on the implemented standard a PDO communication entry has a
#       reserved byte at subindex 4


class PdoNode(collections.Mapping):
    """Represents a slave unit."""

    def __init__(self, node):
        self.network = None
        self.node = node
        self.rx = Maps(0x1400, 0x1600, self)
        self.tx = Maps(0x1800, 0x1A00, self)

    def __iter__(self):
        for pdo_maps in (self.rx, self.tx):
            for pdo_map in pdo_maps.values():
                for var in pdo_map.map:
                    yield var.name

    def __getitem__(self, key):
        for pdo_maps in (self.rx, self.tx):
            for pdo_map in pdo_maps.values():
                for var in pdo_map.map:
                    if var.name == key:
                        return var
        raise KeyError("%s was not found in any map" % key)

    def __len__(self):
        count = 0
        for pdo_maps in (self.rx, self.tx):
            for pdo_map in pdo_maps.values():
                count += len(pdo_map)
        return count

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
                                              signalSize=var.length,
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
        for idx in range(0x200):
            com_index = com_offset + idx
            map_index = map_offset + idx
            if com_index in pdo_node.node.object_dictionary:
                com_entry = pdo_node.node.object_dictionary[com_index]
                if com_entry.subindices[1].default:
                    cob_id = com_entry.subindices[1].default
                else:
                    logger.warning("Don't know how to handle communication "
                                   "index 0x{:X}".format(com_index))
                    continue
                self.maps[com_index] = Map(cob_id,
                                           pdo_node,
                                           com_index,
                                           map_index)

    def __getitem__(self, key):
        return self.maps[key]

    def __iter__(self):
        return iter(self.maps)

    def __len__(self):
        return len(self.maps)


class Map(object):
    """One message which can have up to 8 bytes of variables mapped."""

    def __init__(self, cob_id, pdo_node, com_index, map_index):
        self.pdo_node = pdo_node
        self.com_index = com_index
        self.map_index = map_index
        com_entry = pdo_node.node.object_dictionary[com_index]
        #: If this map is valid
        self.enabled = True
        #: COB-ID for this PDO
        self.cob_id = cob_id
        #: Is the remote transmit request (RTR) allowed for this PDO
        self.rtr_allowed = True
        #: Transmission type (0-255)
        self.trans_type = com_entry.subindices[2]
        #: Inhibit Time (optional) (in 100us)
        if 3 in com_entry.subindices:
            self.inhibit_time = com_entry.subindices[3]
        else:
            self.inhibit_time = None
        #: Event timer (optional) (in ms)
        if 5 in com_entry.subindices:
            self.event_timer = com_entry.subindices[5]
        else:
            self.event_timer = None
        #: List of variables mapped to this PDO. PDOs deal with volatile data
        # thus we save the information as tuple (index, sub, length), the
        # actual data must be looked up in the data store of the node
        self.map = []
        # Iterate over the sub-indices describing the map
        for map_entry in pdo_node.node.object_dictionary[map_index]:
            # The routing hex is 4 byte long and holds index (16bit), subindex
            # (8 bits) and bit length (8 bits)
            # TODO: We shouldn't use just default, because the actual value can
            # be overwritten via SDO
            routing_hex = map_entry.default
            index = (routing_hex >> 16) & 0xFFFF
            subindex = (routing_hex >> 8) & 0xFF
            length = routing_hex & 0xFF
            self.map.append((index, subindex, length))
        #: Timestamp of last received message
        self.timestamp = 0
        #: Period of receive message transmission in seconds
        self.period = None
        self.callbacks = []
        self.receive_condition = threading.Condition()
        self.is_received = False
        self._task = None
        self._register_pdo()

    def _register_pdo(self):
        # TODO: Install the traps and callbacks for data changes
        pass

    def __getitem__(self, key):
        if isinstance(key, int):
            return self.map[key]
        else:
            raise TypeError("Lookup value must have type int")

    def __iter__(self):
        return iter(self.map)

    def __len__(self):
        return len(self.map)

    def _get_variable(self, index, subindex):
        obj = self.pdo_node.node.object_dictionary[index]
        if isinstance(obj, (objectdictionary.Record, objectdictionary.Array)):
            obj = obj[subindex]
        var = Variable(obj)
        var.msg = self
        return var

    def _update_data_size(self):
        total_length = sum([info[2] for info in self.map])
        self.data = bytearray(total_length)

    @property
    def name(self):
        """A descriptive name of the PDO.

        Examples:
         * TxPDO_0x1542_node4
         * RxPDO_0x1812_node1
        """
        direction = "Rx" if 0x1400 <= self.com_index < 0x1600 else "Tx"
        node_id = self.pdo_node.node.id
        return "%sPDO_0x%X_node%d" % (direction, self.com_index, node_id)

    def on_message(self, can_id, data, timestamp):
        is_transmitting = self._task is not None
        if can_id == self.cob_id and not is_transmitting:
            with self.receive_condition:
                self.is_received = True
                self.data = data
                self.period = timestamp - self.timestamp
                self.timestamp = timestamp
                self.receive_condition.notify_all()
                self._update_mapped_data()

    def _update_mapped_data(self):
        # Map the received byte data according to the mapping rules of this PDO
        data_start = 0
        for index, subindex, length in self.map:
            data_end = data_start + length
            self.pdo_node.node.set_data(index, subindex,
                                        self.data[data_start:data_end])
            data_start = data_end
        # Data has been updated, now we can invoke the callbacks
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
        # TODO: Do we still need this method?
        pass

    def save(self):
        """Save PDO configuration for this map using SDO."""
        # TODO: Adapt to new class API
        pass

    def clear(self):
        """Clear all variables from this map."""
        self.map = []
        self.length = 0

    def add_variable(self, index, subindex=0, length=None):
        """Add a variable from object dictionary as the next entry.

        :param index: Index of variable as name or number
        :param subindex: Sub-index of variable as name or number
        :param int length: Size of data in number of bits
        :type index: :class:`str` or :class:`int`
        :type subindex: :class:`str` or :class:`int`
        :return: Variable that was added
        :rtype: canopen.pdo.Variable
        """
        try:
            var = self._get_variable(index, subindex)
            var.offset = self.length
            if length is not None:
                # Custom bit length
                var.length = length
            else:
                length = var.length
            logger.info("Adding %s (0x%X:%d) to PDO map",
                        var.name, var.od.index, var.od.subindex)
            self.map.append(var)
        except KeyError as exc:
            logger.warning("%s", exc)
            var = None

        self.length += length
        self._update_data_size()
        if self.length > 64:
            logger.warning("Max size of PDO exceeded (%d > 64)", self.length)
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

        self._task = self.pdo_node.network.send_periodic(
            self.cob_id, self.data, self.period)

    def stop(self):
        """Stop transmission."""
        if self._task is not None:
            self._task.stop()
            self._task = None

    def update(self):
        """Update periodic message with new data."""
        if self._task is not None:
            self._task.update(self.data)

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


class Variable(variable.Variable):
    """One object dictionary variable mapped to a PDO."""

    def __init__(self, od):
        self.msg = None
        #: Location of variable in the message in bits
        self.offset = None
        self.name = od.name
        self.length = len(od)
        if isinstance(od.parent, (objectdictionary.Record,
                                  objectdictionary.Array)):
            self.name = od.parent.name + "." + self.name
        variable.Variable.__init__(self, od)

    def get_data(self):
        """Reads the PDO variable from the last received message.

        :return: Variable value as :class:`bytes`.
        :rtype: bytes
        """
        byte_offset, bit_offset = divmod(self.offset, 8)

        if bit_offset or self.length % 8:
            # Need information of the current variable type (unsigned vs signed)
            od_struct = self.od.STRUCT_TYPES[self.od.data_type]
            data = od_struct.unpack_from(self.msg.data, byte_offset)[0]
            # Shift and mask to get the correct values
            data = (data >> bit_offset) & ((1 << self.length) - 1)
            # Check if the variable is signed and if the data is negative prepend signedness
            if od_struct.format.islower() and (1 << (self.length - 1)) < data:
                # fill up the rest of the bits to get the correct signedness
                data = data | (~((1 << self.length) - 1))
            data = od_struct.pack(data)
        else:
            data = self.msg.data[byte_offset:byte_offset + len(self.od) // 8]

        return data

    def set_data(self, data):
        """Set for the given variable the PDO data.

        :param bytes data: Value for the PDO variable in the PDO message as :class:`bytes`.
        """
        byte_offset, bit_offset = divmod(self.offset, 8)
        logger.debug("Updating %s to %s in message 0x%X",
                     self.name, binascii.hexlify(data), self.msg.cob_id)

        if bit_offset or self.length % 8:
            cur_msg_data = self.msg.data[byte_offset:byte_offset + len(self.od) // 8]
            # Need information of the current variable type (unsigned vs signed)
            od_struct = self.od.STRUCT_TYPES[self.od.data_type]
            cur_msg_data = od_struct.unpack(cur_msg_data)[0]
            # data has to have the same size as old_data
            data = od_struct.unpack(data)[0]
            # Mask out the old data value
            # At the end we need to mask for correct variable length (bitwise operation failure)
            shifted = (((1 << self.length) - 1) << bit_offset) & ((1 << len(self.od)) - 1)
            bitwise_not = (~shifted) & ((1 << len(self.od)) - 1)
            cur_msg_data = cur_msg_data & bitwise_not
            # Set the new data on the correct position
            data = (data << bit_offset) | cur_msg_data
            data = od_struct.pack_into(self.msg.data, byte_offset, data)
        else:
            self.msg.data[byte_offset:byte_offset + len(data)] = data

        self.msg.update()
