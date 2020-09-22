import threading
import math
try:
    from collections.abc import Mapping
except ImportError:
    from collections import Mapping
import logging
import binascii

from ..sdo import SdoAbortedError
from .. import objectdictionary
from .. import variable

PDO_NOT_VALID = 1 << 31
RTR_NOT_ALLOWED = 1 << 30

logger = logging.getLogger(__name__)


class PdoBase(Mapping):
    """Represents the base implementation for the PDO object.

    :param object node:
        Parent object associated with this PDO instance
    """

    def __init__(self, node):
        self.network = None
        self.map = None  # instance of Maps
        self.node = node

    def __iter__(self):
        return iter(self.map)

    def __getitem__(self, key):
        if isinstance(key, int) and (0x1A00 <= key <= 0x1BFF or   # By TPDO ID (512)
                                     0x1600 <= key <= 0x17FF or   # By RPDO ID (512)
                                     0 < key <= 512):             # By PDO Index
            return self.map[key]
        else:
            for pdo_map in self.map.values():
                try:
                    return pdo_map[key]
                except KeyError:
                    # ignore if one specific PDO does not have the key and try the next one
                    continue
        raise KeyError("PDO: {0} was not found in any map".format(key))

    def __len__(self):
        return len(self.map)

    def read(self):
        """Read PDO configuration from node using SDO."""
        for pdo_map in self.map.values():
            pdo_map.read()

    def save(self):
        """Save PDO configuration to node using SDO."""
        for pdo_map in self.map.values():
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
        for pdo_map in self.map.values():
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
        """Stop all running tasks."""
        for pdo_map in self.map.values():
            pdo_map.stop()


class Maps(Mapping):
    """A collection of transmit or receive maps."""

    def __init__(self, com_offset, map_offset, pdo_node, cob_base=None):
        """
        :param com_offset:
        :param map_offset:
        :param pdo_node:
        :param cob_base:
        """
        self.maps = {}
        for map_no in range(512):
            if com_offset + map_no in pdo_node.node.object_dictionary:
                new_map = Map(
                    pdo_node,
                    pdo_node.node.sdo[com_offset + map_no],
                    pdo_node.node.sdo[map_offset + map_no])
                # Generate default COB-IDs for predefined connection set
                if cob_base is not None and map_no < 4:
                    new_map.predefined_cob_id = cob_base + map_no * 0x100 + pdo_node.node.id
                self.maps[map_no + 1] = new_map

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
        #: Default COB-ID if this PDO is part of the pre-defined connection set
        self.predefined_cob_id = None
        #: Is the remote transmit request (RTR) allowed for this PDO
        self.rtr_allowed = True
        #: Transmission type (0-255)
        self.trans_type = None
        #: Inhibit Time (optional) (in 100us)
        self.inhibit_time = None
        #: Event timer (optional) (in ms)
        self.event_timer = None
        #: Ignores SYNC objects up to this SYNC counter value (optional)
        self.sync_start_value = None
        #: List of variables mapped to this PDO
        self.map = []
        self.length = 0
        #: Current message data
        self.data = bytearray()
        #: Timestamp of last received message
        self.timestamp = None
        #: Period of receive message transmission in seconds
        self.period = None
        self.callbacks = []
        self.receive_condition = threading.Condition()
        self.is_received = False
        self._task = None

    def __getitem_by_index(self, value):
        valid_values = []
        for var in self.map:
            if var.length:
                valid_values.append(var.index)
                if var.index == value:
                    return var
        raise KeyError('{0} not found in map. Valid entries are {1}'.format(
            value, ', '.join(str(v) for v in valid_values)))

    def __getitem_by_name(self, value):
        valid_values = []
        for var in self.map:
            if var.length:
                valid_values.append(var.name)
                if var.name == value:
                    return var
        raise KeyError('{0} not found in map. Valid entries are {1}'.format(
            value, ', '.join(valid_values)))

    def __getitem__(self, key):
        var = None
        if isinstance(key, int):
            # there is a maximum available of 8 slots per PDO map
            if key in range(0, 8):
                var = self.map[key]
            else:
                var = self.__getitem_by_index(key)
        else:
            try:
                var = self.__getitem_by_index(int(key, 16))
            except ValueError:
                var = self.__getitem_by_name(key)
        return var

    def __iter__(self):
        return iter(self.map)

    def __len__(self):
        return len(self.map)

    def _get_variable(self, index, subindex):
        obj = self.pdo_node.node.object_dictionary[index]
        if isinstance(obj, (objectdictionary.Record, objectdictionary.Array)):
            obj = obj[subindex]
        var = Variable(obj)
        var.pdo_parent = self
        return var

    def _fill_map(self, needed):
        """Fill up mapping array to required length."""
        logger.info("Filling up fixed-length mapping array")
        while len(self.map) < needed:
            # Generate a dummy mapping for an invalid object with zero length.
            obj = objectdictionary.Variable('Dummy', 0, 0)
            var = Variable(obj)
            var.length = 0
            self.map.append(var)

    def _update_data_size(self):
        self.data = bytearray(int(math.ceil(self.length / 8.0)))

    @property
    def name(self):
        """A descriptive name of the PDO.

        Examples:
         * TxPDO1_node4
         * RxPDO4_node1
         * Unknown
        """
        if not self.cob_id:
            return "Unknown"
        direction = "Tx" if self.cob_id & 0x80 else "Rx"
        map_id = self.cob_id >> 8
        if direction == "Rx":
            map_id -= 1
        node_id = self.cob_id & 0x7F
        return "%sPDO%d_node%d" % (direction, map_id, node_id)

    def on_message(self, can_id, data, timestamp):
        is_transmitting = self._task is not None
        if can_id == self.cob_id and not is_transmitting:
            with self.receive_condition:
                self.is_received = True
                self.data = data
                if self.timestamp is not None:
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
        self.cob_id = cob_id & 0x1FFFFFFF
        logger.info("COB-ID is 0x%X", self.cob_id)
        self.enabled = cob_id & PDO_NOT_VALID == 0
        logger.info("PDO is %s", "enabled" if self.enabled else "disabled")
        self.rtr_allowed = cob_id & RTR_NOT_ALLOWED == 0
        logger.info("RTR is %s", "allowed" if self.rtr_allowed else "not allowed")
        self.trans_type = self.com_record[2].raw
        logger.info("Transmission type is %d", self.trans_type)
        if self.trans_type >= 254:
            try:
                self.inhibit_time = self.com_record[3].raw
            except (KeyError, SdoAbortedError) as e:
                logger.info("Could not read inhibit time (%s)", e)
            else:
                logger.info("Inhibit time is set to %d ms", self.inhibit_time)

            try:
                self.event_timer = self.com_record[5].raw
            except (KeyError, SdoAbortedError) as e:
                logger.info("Could not read event timer (%s)", e)
            else:
                logger.info("Event timer is set to %d ms", self.event_timer)

            try:
                self.sync_start_value = self.com_record[6].raw
            except (KeyError, SdoAbortedError) as e:
                logger.info("Could not read SYNC start value (%s)", e)
            else:
                logger.info("SYNC start value is set to %d ms", self.sync_start_value)

        self.clear()
        nof_entries = self.map_array[0].raw
        for subindex in range(1, nof_entries + 1):
            value = self.map_array[subindex].raw
            index = value >> 16
            subindex = (value >> 8) & 0xFF
            size = value & 0xFF
            if hasattr(self.pdo_node.node, "curtis_hack") and self.pdo_node.node.curtis_hack:  # Curtis HACK: mixed up field order
                index = value & 0xFFFF
                subindex = (value >> 16) & 0xFF
                size = (value >> 24) & 0xFF
            if index and size:
                self.add_variable(index, subindex, size)

        if self.enabled:
            self.pdo_node.network.subscribe(self.cob_id, self.on_message)

    def save(self):
        """Save PDO configuration for this map using SDO."""
        logger.info("Setting COB-ID 0x%X and temporarily disabling PDO",
                    self.cob_id)
        self.com_record[1].raw = self.cob_id | PDO_NOT_VALID
        if self.trans_type is not None:
            logger.info("Setting transmission type to %d", self.trans_type)
            self.com_record[2].raw = self.trans_type
        if self.inhibit_time is not None:
            logger.info("Setting inhibit time to %d us", (self.inhibit_time * 100))
            self.com_record[3].raw = self.inhibit_time
        if self.event_timer is not None:
            logger.info("Setting event timer to %d ms", self.event_timer)
            self.com_record[5].raw = self.event_timer
        if self.sync_start_value is not None:
            logger.info("Setting SYNC start value to %d", self.sync_start_value)
            self.com_record[6].raw = self.sync_start_value

        if self.map is not None:
            try:
                self.map_array[0].raw = 0
            except SdoAbortedError:
                # WORKAROUND for broken implementations: If the array has a
                # fixed number of entries (count not writable), generate dummy
                # mappings for an invalid object 0x0000:00 to overwrite any
                # excess entries with all-zeros.
                self._fill_map(self.map_array[0].raw)
            subindex = 1
            for var in self.map:
                logger.info("Writing %s (0x%X:%d, %d bits) to PDO map",
                            var.name, var.index, var.subindex, var.length)
                if hasattr(self.pdo_node.node, "curtis_hack") and self.pdo_node.node.curtis_hack:  # Curtis HACK: mixed up field order
                    self.map_array[subindex].raw = (var.index |
                                                    var.subindex << 16 |
                                                    var.length << 24)
                else:
                    self.map_array[subindex].raw = (var.index << 16 |
                                                    var.subindex << 8 |
                                                    var.length)
                subindex += 1
            try:
                self.map_array[0].raw = len(self.map)
            except SdoAbortedError as e:
                # WORKAROUND for broken implementations: If the array
                # number-of-entries parameter is not writable, we have already
                # generated the required number of mappings above.
                if e.code != 0x06010002:
                    # Abort codes other than "Attempt to write a read-only
                    # object" should still be reported.
                    raise
            self._update_data_size()

        if self.enabled:
            logger.info("Enabling PDO")
            self.com_record[1].raw = self.cob_id
            self.pdo_node.network.subscribe(self.cob_id, self.on_message)

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
            if subindex and isinstance(subindex, int):
                # Force given subindex upon variable mapping, for misguided implementations
                var.subindex = subindex
            var.offset = self.length
            if length is not None:
                # Custom bit length
                var.length = length
            # We want to see the bit fields within the PDO
            start_bit = var.offset
            end_bit = start_bit + var.length - 1
            logger.info("Adding %s (0x%X:%d) at bits %d - %d to PDO map",
                        var.name, var.index, var.subindex, start_bit, end_bit)
            self.map.append(var)
            self.length += var.length
        except KeyError as exc:
            logger.warning("%s", exc)
            var = None
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
        #: PDO object that is associated with this Variable Object
        self.pdo_parent = None
        #: Location of variable in the message in bits
        self.offset = None
        self.length = len(od)
        variable.Variable.__init__(self, od)

    def get_data(self):
        """Reads the PDO variable from the last received message.

        :return: Variable value as :class:`bytes`.
        :rtype: bytes
        """
        byte_offset, bit_offset = divmod(self.offset, 8)

        if bit_offset or self.length % 8:
            # Need information of the current variable type (unsigned vs signed)
            data_type = self.od.data_type
            if data_type == objectdictionary.BOOLEAN:
                # A boolean type needs to be treated as an U08
                data_type = objectdictionary.UNSIGNED8
            od_struct = self.od.STRUCT_TYPES[data_type]
            data = od_struct.unpack_from(self.pdo_parent.data, byte_offset)[0]
            # Shift and mask to get the correct values
            data = (data >> bit_offset) & ((1 << self.length) - 1)
            # Check if the variable is signed and if the data is negative prepend signedness
            if od_struct.format.islower() and (1 << (self.length - 1)) < data:
                # fill up the rest of the bits to get the correct signedness
                data = data | (~((1 << self.length) - 1))
            data = od_struct.pack(data)
        else:
            data = self.pdo_parent.data[byte_offset:byte_offset + len(self.od) // 8]

        return data

    def set_data(self, data):
        """Set for the given variable the PDO data.

        :param bytes data: Value for the PDO variable in the PDO message as :class:`bytes`.
        """
        byte_offset, bit_offset = divmod(self.offset, 8)
        logger.debug("Updating %s to %s in %s",
                     self.name, binascii.hexlify(data), self.pdo_parent.name)

        if bit_offset or self.length % 8:
            cur_msg_data = self.pdo_parent.data[byte_offset:byte_offset + len(self.od) // 8]
            # Need information of the current variable type (unsigned vs signed)
            data_type = self.od.data_type
            if data_type == objectdictionary.BOOLEAN:
                # A boolean type needs to be treated as an U08
                data_type = objectdictionary.UNSIGNED8
            od_struct = self.od.STRUCT_TYPES[data_type]
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
            data = od_struct.pack_into(self.pdo_parent.data, byte_offset, data)
        else:
            self.pdo_parent.data[byte_offset:byte_offset + len(data)] = data

        self.pdo_parent.update()
