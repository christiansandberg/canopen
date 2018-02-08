import threading
import collections
import logging

from . import objectdictionary
from . import variable


PDO_NOT_VALID = 1 << 31
RTR_NOT_ALLOWED = 1 << 30


logger = logging.getLogger(__name__)

# TODO: Depending on the implemented standard a PDO communication entry has a
#       reserved byte at subindex 4
# TODO: Support the inhibit time constraint for transmission
# TODO: Support the event timer constraint for transmission


def create_pdos(com_offset, map_offset, pdo_node, direction):
    maps = {}
    direction_lower = direction.lower()
    if direction_lower in ["transmit", "tx"]:
        PDO = TPDO
    elif direction_lower in ["receive", "rx"]:
        PDO = RPDO
    else:
        logger.critical("Direction %s is not supported" % direction)
        return maps
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
            maps[com_index] = PDO(cob_id, pdo_node, com_index, map_index)
    return maps


class RemotePdoNode(collections.Mapping):
    """Represents a slave unit."""
    # TODO: Remote nodes behave different, because we don't own the data that
    #       is sent or received.
    def __init__(self, node):
        self.network = None
        self.node = node


class LocalPdoNode(collections.Mapping):
    """Represents a slave unit."""

    def __init__(self, node):
        self.network = None
        self.node = node
        self.rx = create_pdos(0x1400, 0x1600, self, "Rx")
        self.tx = create_pdos(0x1800, 0x1A00, self, "Tx")

    def __iter__(self):
        # TODO: What do we want to yield here? The communication parameters or
        #       the mapped object dictionary indices?
        raise StopIteration

    def __getitem__(self, key):
        # TODO: What do we want to get here? The communication parameters or
        #       the mapped object dictionary indices?
        raise KeyError("%s was not found in any map" % key)

    def __len__(self):
        count = 0
        for pdo_maps in (self.rx, self.tx):
            for pdo_map in pdo_maps.values():
                count += len(pdo_map)
        return count

    def export(self, filename):
        """Export current configuration to a database file.

        :param str filename:
            Filename to save to (e.g. DBC, DBF, ARXML, KCD etc)

        :return: The CanMatrix object created
        :rtype: canmatrix.canmatrix.CanMatrix
        """
        # TODO: Retrieve the info from self.node.object_dictionary with the
        #       help of com_index and map_index of the PDO classes and create
        #       the canmatrix data type
        raise NotImplementedError

    def stop(self):
        """Stop transmission of all TPDOs."""
        for tpdo in self.tx.values():
            tpdo.stop()


class PDOBase(object):
    """One message which can have up to 8 bytes of variables mapped."""

    def __init__(self, cob_id, pdo_node, com_index, map_index):
        self.cob_id = cob_id
        self.pdo_node = pdo_node
        self.com_index = com_index
        self.map_index = map_index
        #: If this map is valid
        self.enabled = True
        self.map = []
        # Iterate over the sub-indices describing the map
        for map_entry in pdo_node.node.object_dictionary[map_index].values():
            # The routing hex is 4 byte long and holds index (16bit), subindex
            # (8 bits) and bit length (8 bits)
            # TODO: We shouldn't use just default, because the actual value can
            # be overwritten via SDO
            # TODO: We need to handle dummy mapping entries
            routing_hex = map_entry.default
            index = (routing_hex >> 16) & 0xFFFF
            subindex = (routing_hex >> 8) & 0xFF
            length = routing_hex & 0xFF
            self.map.append((index, subindex, length))
        #: Time stamp of last sent or received message
        self.timestamp = 0
        self.callbacks = []

    def setup_pdo(self):
        # TODO: Install the traps and callbacks for data changes
        raise NotImplementedError

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
        var = variable.Variable(obj)
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

    def add_callback(self, callback):
        """Add a callback which will be called when a message is sent or
        received.

        :param callback:
            The function that will be called. The function must accept one
            argument, which will be the PDO class itself.
        """
        self.callbacks.append(callback)

    def clear(self):
        """Clear all variables from this map."""
        self.map = []


class TPDO(PDOBase):
    """Transmit PDO specialization of the PDOBase class."""
    # The transmission type constants
    # TODO: The transmission type can be more fine grained
    TT_UNDEFINED = 0x00
    TT_RTR_TRIGGERED = 0x01
    TT_EVENT_TRIGGERED = 0x02
    TT_SYNC_TRIGGERED = 0x04
    TT_CYCLIC = 0x08

    def __init__(self, cob_id, pdo_node, com_index, map_index):
        # TODO: It is not good to use only the default values
        PDOBase.__init__(self, cob_id, pdo_node, com_index, map_index)
        com_entry = pdo_node.node.object_dictionary[com_index]
        #: Is the remote transmit request (RTR) allowed for this PDO
        self.rtr_allowed = True
        #: Transmission type (0-255)
        trans_type_variable = com_entry.subindices[2]
        self.trans_type = self._map_transmission_type(
            trans_type_variable.default)
        #: Inhibit Time (optional) (in 100us)
        if 3 in com_entry.subindices:
            self.inhibit_time = com_entry.subindices[3]
        else:
            self.inhibit_time = None
        #: Event timer (optional) (in ms)
        if 5 in com_entry.subindices:
            self.event_timer = com_entry.subindices[5]
            # TODO: Is this correct?
            self.trans_type |= self.TT_CYCLIC
        else:
            self.event_timer = None
        #: Period of receive message transmission in seconds
        self.period = None
        if self.event_timer:
            self.period = self.event_timer.default / 1000.0
        self._task = None
        self.data = bytes()

    def setup_pdo(self):
        self.data = self._build_data()
        do_setup_traps = False
        if self.trans_type & self.TT_SYNC_TRIGGERED:
            # Subscribe to the SYNC message
            self.pdo_node.network.subscribe(0x80, self.on_sync)
        elif self.trans_type & self.TT_EVENT_TRIGGERED:
            # Register the traps to catch a change of data
            # TODO: The trigger conditions can be specified in the
            #       manufacturer, device and application profiles
            do_setup_traps = True
        elif self.trans_type & self.TT_RTR_TRIGGERED:
            # RTR triggering must be supported
            if self.rtr_allowed:
                # TODO
                pass
        elif self.trans_type & self.TT_CYCLIC:
            # Register the traps to catch a change of data
            do_setup_traps = True
            self.transmit_cyclic()
        else:
            pass

        if do_setup_traps:
            # TODO: We also need traps for the SDO changeable communication
            #       parameters
            traps = self.pdo_node.node.data_store_traps
            for index, subindex, _ in self.map:
                if self.on_value_change not in traps[(index, subindex)]:
                    traps[(index, subindex)].append(self.on_value_change)

    def on_sync(self, can_id, data, timestamp):
        """This is the callback method for when this PDO receives a SYNC
        message. The SYNC triggers the data of the PDO to be sent."""
        self.transmit_once()

    def on_value_change(self, index, subindex, data):
        """This is the callback method for when the internal data of the node
        has changed."""
        self.data = self._build_data()
        if self._task is not None:
            self._task.update(self.data)

    def transmit_once(self):
        """Transmit the message once."""
        self.pdo_node.network.send_message(self.cob_id, self.data)

    def start_cyclic_transmit(self, period=None):
        """Start periodic transmission of the TPDO in a background thread.

        :param float period: Transmission period in seconds
        """
        if period is not None:
            self.period = period

        if not self.period:
            raise ValueError("A valid transmission period has not been given")
        logger.info("Starting %s with a period of %s seconds",
                    self.name, self.period)

        self._task = self.pdo_node.network.send_periodic(
            self.cob_id, self.data, self.period)

    def stop_cyclic_transmit(self):
        """Stop cyclic transmission."""
        if self._task is not None:
            self._task.stop()
            self._task = None

    def update_cyclic_transmit(self):
        """Update cyclic message with new data."""
        if self._task is not None:
            self._task.update(self.data)

    @classmethod
    def _map_transmission_type(cls, ttype):
        ttype_mapped = cls.TT_UNDEFINED
        if ttype <= 0xF0:
            # Transmission is triggered by SYNC messages
            ttype_mapped = cls.TT_SYNC_TRIGGERED
        elif 0xF1 <= ttype <= 0xFB:
            # These are reserved values and currently not supported
            logger.error("Reserved transmission type 0x%X" % ttype)
            ttype_mapped = cls.TT_UNDEFINED
        elif 0xFC <= ttype <= 0xFD:
            # RTR triggered
            ttype_mapped = cls.TT_RTR_TRIGGERED
        else:
            # The transmission is event triggered.
            # TODO: The trigger configuration can be specified in the
            #       manufacturer, device and application profiles
            ttype_mapped = cls.TT_EVENT_TRIGGERED
        return ttype_mapped

    def _build_data(self):
        data = bytes()
        for index, subindex, length in self.map:
            entry_data = self.pdo_node.node.get_data(index, subindex)
            data += entry_data[:length]
        return data


class RPDO(PDOBase):
    """Receive PDO specialization of the PDOBase class."""

    def __init__(self, cob_id, pdo_node, com_index, map_index):
        PDOBase.__init__(self, cob_id, pdo_node, com_index, map_index)
        self.receive_condition = threading.Condition()
        self.is_received = False

    def setup_pdo(self):
        self.pdo_node.network.subscribe(self.cob_id, self.on_message)

    def on_message(self, can_id, data, timestamp):
        # TODO: Invalid data changes shall be answered with an SDO abort
        if can_id == self.cob_id:
            with self.receive_condition:
                self.is_received = True
                self.data = data
                self.timestamp = timestamp
                self.receive_condition.notify_all()
                self._update_mapped_data()

    def _update_mapped_data(self):
        # Map the received byte data according to the mapping rules of this PDO
        data_start = 0
        for index, subindex, length in self.map:
            data_end = data_start + length
            # TODO: This will trigger change callbacks per mapped entry, it is
            # preferable to change the data atomically and then invoke callbacks
            self.pdo_node.node.set_data(index, subindex,
                                        self.data[data_start:data_end])
            data_start = data_end
        # Data has been updated, now we can invoke the callbacks
        for callback in self.callbacks:
            callback(self)

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
