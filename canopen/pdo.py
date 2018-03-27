import collections
from itertools import chain
import logging
import threading

from . import objectdictionary
from .sdo.exceptions import SdoAbortedError


PDO_NOT_VALID = 1 << 31
RTR_NOT_ALLOWED = 1 << 30


logger = logging.getLogger(__name__)

# TODO: Only send and receive messages when in state OPERATIONAL
# TODO: Support the inhibit time constraint for transmission
# TODO: Support more fine grained transmission types
# TODO: Implement LocalPdoNode export
# TODO: We need to handle dummy mapping entries
# TODO: Support more sophisticated trigger mechanisms
# TODO: Support RTR trigger correctly
# TODO: Invalid data changes shall be answered with an SDO abort


def create_pdos(com_offset, map_offset, pdo_node, direction, is_remote):
    maps = {}
    direction_lower = direction.lower()
    if direction_lower in ["transmit", "tx"]:
        if is_remote:
            PDO = RemoteTPDO
        else:
            PDO = LocalTPDO
    elif direction_lower in ["receive", "rx"]:
        if is_remote:
            PDO = RemoteRPDO
        else:
            PDO = LocalRPDO
    else:
        logger.critical("Direction %s is not supported" % direction)
        return maps
    for idx in range(0x200):
        com_index = com_offset + idx
        map_index = map_offset + idx
        if com_index in pdo_node.node.object_dictionary:
            maps[com_index] = PDO(pdo_node, com_index, map_index)
    return maps


class PdoNodeBase(collections.Mapping):
    """Represents a slave unit."""
    def __init__(self, node):
        self.network = None
        self.node = node
        self.subscriptions = set()
        self.rx = {}
        self.tx = {}

    def __iter__(self):
        return chain(iter(sorted(self.rx.keys())),
                     iter(sorted(self.tx.keys())))

    def __getitem__(self, key):
        if key in self.rx:
            return self.rx[key]
        if key in self.tx:
            return self.tx[key]
        raise KeyError("%s was not found in any map" % key)

    def __contains__(self, key):
        return key in self.rx or key in self.tx

    def __len__(self):
        return len(self.rx) + len(self.tx)

    def stop(self):
        pass

    def setup(self):
        for pdos in (self.rx, self.tx):
            for pdo in pdos.values():
                pdo.setup()

    def cleanup(self):
        for pdos in (self.rx, self.tx):
            for pdo in pdos.values():
                pdo.cleanup()

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
        return len(self.rx) + len(self.tx)


class RemotePdoNode(PdoNodeBase):
    """Represents a slave unit."""
    def __init__(self, node):
        PdoNodeBase.__init__(self, node)
        self.rx = create_pdos(0x1400, 0x1600, self, "Rx", is_remote=True)
        # We only want to observe(sniff) the PDOs of another note, so the
        # transit PDOs are treated like receive PDOs too
        self.tx = create_pdos(0x1800, 0x1A00, self, "Rx", is_remote=True)


class LocalPdoNode(PdoNodeBase):
    """Represents a slave unit."""

    def __init__(self, node):
        PdoNodeBase.__init__(self, node)
        self.rx = create_pdos(0x1400, 0x1600, self, "Rx", is_remote=False)
        self.tx = create_pdos(0x1800, 0x1A00, self, "Tx", is_remote=False)

    def export(self, filename):
        """Export current configuration to a database file.

        :param str filename:
            Filename to save to (e.g. DBC, DBF, ARXML, KCD etc)

        :return: The CanMatrix object created
        :rtype: canmatrix.canmatrix.CanMatrix
        """
        raise NotImplementedError

    def stop(self):
        """Stop transmission of all TPDOs."""
        for tpdo in self.tx.values():
            tpdo.stop()


class PDOBase(object):
    """One message which can have up to 8 bytes of variables mapped."""

    def __init__(self, pdo_node, com_index, map_index):
        self.pdo_node = pdo_node
        self.com_index = com_index
        self.map_index = map_index
        #: If this map is valid
        self.enabled = True
        self.map = []
        #: Time stamp of last sent or received message
        self.timestamp = 0
        self.callbacks = []
        self.object_dictionary = pdo_node.node.object_dictionary

    def setup(self):
        logger.info("Setting up PDO 0x%X on node %d" % (
            self.com_index, self.pdo_node.node.id))
        com_entry = self.object_dictionary[self.com_index]
        if 1 in com_entry:
            self.cob_id = com_entry[1].raw
        else:
            logger.error("The PDO at index 0x{:X} does not specify a "
                         "COD-ID".format(self.com_index))
        # Makes sure the node is informed about communication parameter changes
        self.watch_index(self.com_index,
                         self.object_dictionary,
                         self.on_config_change)
        # Makes sure the node is informed about mapping parameter changes
        self.watch_index(self.map_index,
                         self.object_dictionary,
                         self.on_config_change)
        # Create info about how the contents of this PDO are mapped
        self.map = self.create_mapping(self.map_index,
                                       self.object_dictionary)
        logger.info("Internal map: {}".format(self.map))

    def cleanup(self):
        self.map = []
        # Remove the node's callbacks from the objects
        self.unwatch_index(self.com_index,
                           self.object_dictionary,
                           self.on_config_change)
        # Remove the node's callbacks from the objects
        self.unwatch_index(self.map_index,
                           self.object_dictionary,
                           self.on_config_change)

    def reconfigure(self):
        self.cleanup()
        self.setup()

    @classmethod
    def watch_index(cls, index, object_dictionary, callback):
        entry = object_dictionary[index]
        if isinstance(entry, objectdictionary.Variable):
            entry.add_callback(callback)
        else:
            for subindex in entry:
                obj = object_dictionary.get_object(index, subindex)
                obj.add_callback(callback)

    @classmethod
    def unwatch_index(cls, index, object_dictionary, callback):
        entry = object_dictionary[index]
        if isinstance(entry, objectdictionary.Variable):
            entry.remove_callback(callback)
        else:
            for subindex in entry:
                obj = object_dictionary.get_object(index, subindex)
                obj.remove_callback(callback)

    @classmethod
    def create_mapping(cls, map_index, object_dictionary):
        map_entry = object_dictionary[map_index]
        mapping = []
        for map_entry_index in map_entry:
            # The first subindex just holds the count
            if map_entry_index != 0:
                # The routing hex is 4 byte long and holds index (16bit),
                # subindex (8 bits) and bit length (8 bits)
                routing_hex = map_entry[map_entry_index].raw
                index = (routing_hex >> 16) & 0xFFFF
                subindex = (routing_hex >> 8) & 0xFF
                length = int((routing_hex & 0xFF) / 8)
                # Only if there is data to map, i.e. length > 0
                if length > 0:
                    mapping.append((index, subindex, length))
        return mapping

    def on_config_change(self, index, subindex, data):
        logger.info("Change detected")
        do_reconfigure = False
        if index == self.com_index:
            logger.info("Communication parameters for PDO "
                        "0x%X have changed" % self.cob_id)
            do_reconfigure = True
        elif index == self.map_index:
            logger.info("Mapping parameters for PDO "
                        "0x%X have changed" % self.cob_id)
            do_reconfigure = True
        else:
            logger.warning("Bad config callback: Index 0x%X is neither the "
                           "mapping nor the communication parameter of this "
                           "PDO" % self.cob_id)
        if do_reconfigure:
            self.reconfigure()

    def __getitem__(self, key):
        index, subindex, _ = self.map[key]
        return self.object_dictionary.get_object(index, subindex)

    def __iter__(self):
        return iter(self.map)

    def __len__(self):
        return len(self.map)

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

    def remove_callback(self, callback):
        """Remove a callback from the currently registered callbacks.

        :param callback:
            The reference to the callback function.
        """
        self.callbacks.remove(callback)

    def clear(self):
        """Clear all variables from this map."""
        self.map = []


class TPDO(PDOBase):
    """Transmit PDO specialization of the PDOBase class."""
    # The transmission type constants
    TT_UNDEFINED = 0x00
    TT_RTR_TRIGGERED = 0x01
    TT_EVENT_TRIGGERED = 0x02
    TT_SYNC_TRIGGERED = 0x04
    TT_CYCLIC = 0x08

    def __init__(self, pdo_node, com_index, map_index):
        PDOBase.__init__(self, pdo_node, com_index, map_index)
        #: Is the remote transmit request (RTR) allowed for this PDO
        self.rtr_allowed = True
        #: Transmission type (0-255)
        self.trans_type = self.TT_SYNC_TRIGGERED
        self.inhibit_time = None
        self.event_timer = None
        #: Period of receive message transmission in seconds
        self.period = None
        self._task = None
        self.data = bytearray()

    def setup(self):
        PDOBase.setup(self)
        com_entry = self.object_dictionary[self.com_index]
        #: Is the remote transmit request (RTR) allowed for this PDO
        self.rtr_allowed = True
        #: Transmission type (0-255)
        trans_type_variable = com_entry.subindices[2]
        self.trans_type = self._map_transmission_type(
            trans_type_variable.raw)
        #: Inhibit Time (optional) (in 100us)
        if 3 in com_entry.subindices:
            self.inhibit_time = com_entry.subindices[3]
        else:
            self.inhibit_time = None
        #: Event timer (optional) (in ms)
        if 5 in com_entry.subindices:
            self.event_timer = com_entry.subindices[5]
            self.trans_type |= self.TT_CYCLIC
        else:
            self.event_timer = None
        #: Period of receive message transmission in seconds
        self.period = None
        if self.event_timer:
            self.period = self.event_timer.raw / 1000.0
        self.data = self._build_data()
        do_setup_data_traps = False
        if self.trans_type & self.TT_SYNC_TRIGGERED:
            # Subscribe to the SYNC message
            self.pdo_node.network.subscribe(0x80, self.on_sync)
            self.pdo_node.subscriptions.add(0x80)
        if self.trans_type & self.TT_EVENT_TRIGGERED:
            # Register the traps to catch a change of data
            do_setup_data_traps = True
        if self.trans_type & self.TT_RTR_TRIGGERED:
            # RTR triggering must be supported
            if self.rtr_allowed:
                pass
        if self.trans_type & self.TT_CYCLIC:
            # Register the traps to catch a change of data
            do_setup_data_traps = True
            self.start()

        if do_setup_data_traps:
            logger.info("Setting up data traps for node")
            for index, subindex, _ in self.map:
                obj = self.pdo_node.node.get_object(index, subindex)
                if self.on_data_change not in obj.traps:
                    obj.traps.append(self.on_data_change)

    def cleanup(self):
        self.stop()
        for index, subindex, _ in self.map:
            obj = self.pdo_node.node.get_object(index, subindex)
            if self.on_data_change in obj.traps:
                obj.traps.remove(self.on_data_change)
        PDOBase.cleanup(self)

    def on_sync(self, can_id, data, timestamp):
        """This is the callback method for when this PDO receives a SYNC
        message. The SYNC triggers the data of the PDO to be sent."""
        logger.info("Node %d: Transmitting on SYNC request" %
                    self.pdo_node.node.id)
        self.transmit_once()

    def on_data_change(self, index, subindex, value):
        """This is the callback method for when the internal data of the node
        has changed."""
        logger.info("Data change detected")
        logger.info("Old message content {}".format(self.data))
        # Parts of our data changed, the details don't matter, rebuild the data
        new_data = self._build_data()
        if new_data != self.data:
            logger.debug("New message content {}".format(new_data))
            self.data = new_data
            if self._task is not None:
                self._task.update(self.data)

    def transmit_once(self):
        """Transmit the message once."""
        self.pdo_node.network.send_message(self.cob_id, self.data)

    def start(self, period=None):
        """Start periodic transmission of the TPDO in a background thread.

        :param float period: Transmission period in seconds
        """
        if period is not None:
            self.period = period

        if not self.period:
            raise ValueError("A valid transmission period has not been given")
        logger.info("Starting %s with a period of %s seconds, COBID 0x%X",
                    self.name, self.period, self.cob_id)
        logger.info("Data: {}".format(self.data))
        self._task = self.pdo_node.network.send_periodic(
            self.cob_id, self.data, self.period)

    def stop(self):
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
            ttype_mapped = cls.TT_EVENT_TRIGGERED
        return ttype_mapped

    def _build_data(self):
        data = bytearray()
        for index, subindex, length in self.map:
            entry_data = self.pdo_node.node.get_data(index, subindex)
            data += entry_data[:length]
        return data


class RPDO(PDOBase):
    """Receive PDO specialization of the PDOBase class."""

    def __init__(self, pdo_node, com_index, map_index):
        PDOBase.__init__(self, pdo_node, com_index, map_index)
        self.receive_condition = threading.Condition()
        self.is_received = False

    def setup(self):
        PDOBase.setup(self)
        self.pdo_node.network.subscribe(self.cob_id, self.on_message)
        self.pdo_node.subscriptions.add(self.cob_id)

    def cleanup(self):
        self.pdo_node.network.unsubscribe(self.cob_id)
        self.pdo_node.subscriptions.remove(self.cob_id)
        PDOBase.cleanup(self)

    def on_message(self, can_id, data, timestamp):
        logger.info("Received PDO on COBID 0x%X" % can_id)
        logger.info("Data: {}".format(data))
        if can_id == self.cob_id:
            with self.receive_condition:
                self.is_received = True
                self.data = data
                self.timestamp = timestamp
                self.receive_condition.notify_all()
                self._write_data(data)

    def _write_data(self, data):
        logger.info("Updating values in internal data store...")
        # Map the received byte data according to the mapping rules of this PDO
        data_start = 0
        for index, subindex, length in self.map:
            data_end = data_start + length
            obj = self.pdo_node.node.get_object(index, subindex)
            obj.bytes = data[data_start:data_end]
            data_start = data_end
        # Now invoke the PDO specific callbacks
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


class ReadSave():
    def read(self):
        """Read PDO configuration for this PDO using SDO."""
        com_record = self.pdo_node.node.sdo[self.com_index]
        cob_id = com_record[1].raw
        self.cob_id = cob_id & 0x7FF
        logger.info("COB-ID is 0x%X", self.cob_id)
        self.enabled = cob_id & PDO_NOT_VALID == 0
        logger.info("PDO is %s", "enabled" if self.enabled else "disabled")
        self.rtr_allowed = cob_id & RTR_NOT_ALLOWED == 0
        logger.info("RTR is %s",
                    "allowed" if self.rtr_allowed else "not allowed")
        self.trans_type = com_record[2].raw
        logger.info("Transmission type is %d", self.trans_type)
        if self.trans_type >= 254:
            try:
                self.inhibit_time = com_record[3].raw
            except (KeyError, SdoAbortedError) as e:
                logger.info("Could not read inhibit time (%s)", e)
            else:
                logger.info("Inhibit time is set to %d ms", self.inhibit_time)

            try:
                self.event_timer = com_record[5].raw
            except (KeyError, SdoAbortedError) as e:
                logger.info("Could not read event timer (%s)", e)
            else:
                logger.info("Event timer is set to %d ms", self.event_timer)

        self.clear()
        map_array = self.pdo_node.node.sdo[self.map_index]
        nof_entries = map_array[0].raw
        for subindex in range(1, nof_entries + 1):
            value = map_array[subindex].raw
            index = value >> 16
            subindex = (value >> 8) & 0xFF
            length = int((value & 0xFF) / 8)
            self.map.append((index, subindex, length))

        if self.enabled:
            self.pdo_node.network.subscribe(self.cob_id, self.on_message)

    def save(self):
        """Save PDO configuration for this PDO using SDO."""
        logger.info("Setting COB-ID 0x%X and temporarily disabling PDO",
                    self.cob_id)
        com_record = self.pdo_node.node.sdo[self.com_index]
        com_record[1].raw = self.cob_id | PDO_NOT_VALID
        if self.trans_type is not None:
            logger.info("Setting transmission type to %d", self.trans_type)
            com_record[2].raw = self.trans_type
        if self.inhibit_time is not None:
            logger.info("Setting inhibit time to %d us",
                        (self.inhibit_time * 100))
            com_record[3].raw = self.inhibit_time
        if self.event_timer is not None:
            logger.info("Setting event timer to %d ms", self.event_timer)
            com_record[5].raw = self.event_timer

        map_array = self.pdo_node.node.sdo[self.map_index]
        if self.map is not None:
            map_array[0].raw = 0
            map_index = 1
            for index, subindex, length in self.map:
                logger.info("Writing index 0x%X, subindex %d to PDO map",
                            index, subindex)
                map_array[map_index].raw = (index << 16 |
                                            subindex << 8 |
                                            (length * 8))
                map_index += 1
            map_array[0].raw = len(self.map)
            self._update_data_size()

        if self.enabled:
            logger.info("Enabling PDO")
            com_record[1].raw = self.cob_id
            self.pdo_node.network.subscribe(self.cob_id, self.on_message)


class LocalTPDO(TPDO):
    pass


class LocalRPDO(RPDO):
    pass


class RemoteTPDO(TPDO, ReadSave):
    pass


class RemoteRPDO(RPDO, ReadSave):
    pass
