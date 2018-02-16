import threading
import collections
import logging

from . import objectdictionary


PDO_NOT_VALID = 1 << 31
RTR_NOT_ALLOWED = 1 << 30


logger = logging.getLogger(__name__)

# TODO: Only send and receive messages when in state OPERATIONAL
# TODO: Support the inhibit time constraint for transmission
# TODO: Support more fine grained transmission types
# TODO: Implement RemotePdoNode
# TODO: Implement LocalPdoNode.__iter__
# TODO: Implement LocalPdoNode.__getitem__
# TODO: Implement LocalPdoNode.export
# TODO: We need to handle dummy mapping entries
# TODO: Implement update_com_config
# TODO: Implement update_map_config
# TODO: Support more sophisticated trigger mechanisms
# TODO: Support RTR trigger correctly
# TODO: Invalid data changes shall be answered with an SDO abort


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
            if com_entry.subindices[1].value:
                cob_id = com_entry.subindices[1].value
            else:
                logger.warning("Don't know how to handle communication "
                               "index 0x{:X}".format(com_index))
                continue
            maps[com_index] = PDO(cob_id, pdo_node, com_index, map_index)
    return maps


class RemotePdoNode(collections.Mapping):
    """Represents a slave unit."""
    def __init__(self, node):
        self.network = None
        self.node = node
        self.rx = {}
        self.tx = {}

    def __iter__(self):
        raise StopIteration

    def __getitem__(self, key):
        raise KeyError("%s was not found in any map" % key)

    def __len__(self):
        count = 0
        for pdo_maps in (self.rx, self.tx):
            for pdo_map in pdo_maps.values():
                count += len(pdo_map)
        return count

    def setup(self):
        pass

    def stop(self):
        pass


class LocalPdoNode(collections.Mapping):
    """Represents a slave unit."""

    def __init__(self, node):
        self.network = None
        self.node = node
        self.rx = create_pdos(0x1400, 0x1600, self, "Rx")
        self.tx = create_pdos(0x1800, 0x1A00, self, "Tx")

    def __iter__(self):
        raise StopIteration

    def __getitem__(self, key):
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
        raise NotImplementedError

    def stop(self):
        """Stop transmission of all TPDOs."""
        for tpdo in self.tx.values():
            tpdo.stop_cyclic_transmit()

    def setup(self):
        for pdos in (self.rx, self.tx):
            for pdo in pdos.values():
                pdo.setup()


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
        #: Time stamp of last sent or received message
        self.timestamp = 0
        self.callbacks = []
        self.subscriptions = set()

    def setup(self):
        logger.info("Setting up PDO 0x%X on node %d" % (
            self.com_index, self.pdo_node.node.id))
        com_entry = self.pdo_node.node.object_dictionary[self.com_index]
        map_entry = self.pdo_node.node.object_dictionary[self.map_index]
        com_info_count = com_entry[0].value
        map_info_count = map_entry[0].value
        traps = self.pdo_node.node.data_store_traps
        # Makes sure the node is informed about communication parameter changes
        for com_subentry_index in range(0, com_info_count+1):
            if self.on_config_change not in traps[(self.com_index, com_subentry_index)]:
                traps[(self.com_index, com_subentry_index)].append(self.on_config_change)
        # Makes sure the node is informed about mapping parameter changes
        for map_subentry_index in range(0, map_info_count+1):
            if self.on_config_change not in traps[(self.map_index, map_subentry_index)]:
                traps[(self.map_index, map_subentry_index)].append(self.on_config_change)
        # Create info about how the contents of this PDO are mapped
        for map_entry_index in range(1, map_info_count+1):
            # The routing hex is 4 byte long and holds index (16bit), subindex
            # (8 bits) and bit length (8 bits)
            routing_hex = map_entry[map_entry_index].value
            index = (routing_hex >> 16) & 0xFFFF
            subindex = (routing_hex >> 8) & 0xFF
            length = int((routing_hex & 0xFF) / 8)
            self.map.append((index, subindex, length))
        logger.info("Internal map: {}".format(self.map))

    def on_config_change(self, transaction):
        logger.info("Change detected")
        com_index_already_updated = False
        map_index_already_updated = False
        for index, _, _ in transaction:
            if index == self.com_index and not com_index_already_updated:
                com_index_already_updated = True
                logger.info("Communication parameters for PDO "
                            "0x%X have changed" % self.cob_id)
            if index == self.map_index and not map_index_already_updated:
                map_index_already_updated = True
                logger.info("Mapping parameters for PDO "
                            "0x%X have changed" % self.cob_id)

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
        var = self.pdo_node.node.object_dictionary[index]
        if isinstance(var, (objectdictionary.Record, objectdictionary.Array)):
            var = var[subindex]
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
    TT_UNDEFINED = 0x00
    TT_RTR_TRIGGERED = 0x01
    TT_EVENT_TRIGGERED = 0x02
    TT_SYNC_TRIGGERED = 0x04
    TT_CYCLIC = 0x08

    def __init__(self, cob_id, pdo_node, com_index, map_index):
        PDOBase.__init__(self, cob_id, pdo_node, com_index, map_index)
        com_entry = pdo_node.node.object_dictionary[com_index]
        #: Is the remote transmit request (RTR) allowed for this PDO
        self.rtr_allowed = True
        #: Transmission type (0-255)
        trans_type_variable = com_entry.subindices[2]
        self.trans_type = self._map_transmission_type(
            trans_type_variable.value)
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
            self.period = self.event_timer.value / 1000.0
        self._task = None
        self.data = bytes()

    def setup(self):
        PDOBase.setup(self)
        self.data = self._build_data()
        do_setup_data_traps = False
        if self.trans_type & self.TT_SYNC_TRIGGERED:
            # Subscribe to the SYNC message
            self.pdo_node.network.subscribe(0x80, self.on_sync)
            self.subscriptions.add(0x80)
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
            self.start_cyclic_transmit()

        if do_setup_data_traps:
            logger.info("Setting up data traps for node")
            traps = self.pdo_node.node.data_store_traps
            for index, subindex, _ in self.map:
                if self.on_data_change not in traps[(index, subindex)]:
                    traps[(index, subindex)].append(self.on_data_change)

    def on_sync(self, can_id, data, timestamp):
        """This is the callback method for when this PDO receives a SYNC
        message. The SYNC triggers the data of the PDO to be sent."""
        logger.info("Node %d: Transmitting on SYNC request" %
                    self.pdo_node.node.id)
        self.transmit_once()

    def on_data_change(self, transaction):
        """This is the callback method for when the internal data of the node
        has changed."""
        logger.info("Data change detected")
        logger.info("Old message content {}".format(self.data))
        # Parts of our data changed, the details don't matter, rebuild the data
        self.data = self._build_data()
        logger.info("New message content {}".format(self.data))
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
        logger.info("Starting %s with a period of %s seconds, COBID 0x%X",
                    self.name, self.period, self.cob_id)
        logger.info("Data: {}".format(self.data))
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

    def setup(self):
        PDOBase.setup(self)
        self.pdo_node.network.subscribe(self.cob_id, self.on_message)
        self.subscriptions.add(self.cob_id)

    def on_message(self, can_id, data, timestamp):
        logger.info("Received PDO on COBID 0x%X" % can_id)
        logger.info("Data: {}".format(data))
        if can_id == self.cob_id:
            with self.receive_condition:
                self.is_received = True
                self.data = data
                self.timestamp = timestamp
                self.receive_condition.notify_all()
                self.data_transaction(data)

    def data_transaction(self, data):
        logger.info("Updating values in internal data store...")
        # Map the received byte data according to the mapping rules of this PDO
        data_start = 0
        transaction = []
        for index, subindex, length in self.map:
            data_end = data_start + length
            transaction.append((index, subindex,
                                self.data[data_start:data_end]))
            data_start = data_end
        # First execute the node data transaction
        self.pdo_node.node.data_transaction(transaction)
        # Then invoke the PDO specific callbacks
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
