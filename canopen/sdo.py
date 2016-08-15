import collections
import struct
import time
import logging
import threading
from canopen import objectdictionary


SDO_STRUCT = struct.Struct("<BHBL")


class Node(collections.Mapping):

    def __init__(self, node_id, object_dictionary, network):
        self.node_id = node_id
        self.object_dictionary = object_dictionary
        self.network = network
        self.response_received = threading.Condition()

    def on_response(self, msg):
        with self.response_received:
            self.response = msg
            self.response_received.notify_all()

    def query(self, sdo_request):
        """Send an SDO query, check the response and return the raw data."""
        attempts_left = 5
        while attempts_left:
            self.network.send_message(0x600 + self.node_id, sdo_request)

            # Wait for node to respond
            with self.response_received:
                self.response = None
                self.response_received.wait(0.2)

            if self.response:
                attempts_left = 0
            else:
                attempts_left -= 1

        if not self.response:
            raise SdoCommunicationError("No SDO response received")

        command, index, subindex, value = SDO_STRUCT.unpack(self.response.data)

        """
        # Check that the message is for us
        if isinstance(sdo_request, SDO) and (
            sdo_response.index != sdo_request.index or
            sdo_response.subindex != sdo_request.subindex):
            raise SDOCommunicationError((
                "Node returned a value for "
                "0x{0.index:X}:{0.subindex:d} instead, "
                "maybe there is another SDO master communicating "
                "on the same SDO channel?").format(sdo_response))
        """

        # Check abort code and raise appropriate exceptions
        if command == 0x80:
            abort_code = value
            if abort_code == 0x06090011 or abort_code == 0x06020000:
                raise KeyError("0x{:X}:{:d} does not exist".format(index, subindex))
            #elif abort_code == 0x06090030:
            #    raise ValueError("Value range of parameter exceeded")
            else:
                raise SdoAbortedError(abort_code)

        return self.response.data

    def __getitem__(self, index):
        return Group(self, self.object_dictionary[index])

    def __iter__(self):
        return iter(self.object_dictionary)

    def __len__(self):
        return len(self.object_dictionary)


class Group(collections.Mapping):

    def __init__(self, node, od_group):
        self.node = node
        self.od = od_group

    def __getitem__(self, subindex):
        if self.od.is_array and isinstance(subindex, int) and subindex > 0:
            # Create a new parameter instance
            par = Parameter(self.node, self.od[1])
            # Set correct subindex
            par.subindex = subindex
            return par
        else:
            return Parameter(self.node, self.od[subindex])

    def __iter__(self):
        if self.od.is_array:
            # Return [1, 2, 3, ..., n] where n is the last subindex
            return iter(range(1, len(self) + 1))
        else:
            return iter(self.od)

    def __len__(self):
        return self[0].raw if self.od.is_array else len(self.od)

    def __contains__(self, subindex):
        if self.od.is_array and isinstance(subindex, int):
            return subindex <= len(self)
        else:
            return subindex in self.od


class Parameter(object):

    DATA_TYPES = {
        objectdictionary.INTEGER8: "b",
        objectdictionary.INTEGER16: "h",
        objectdictionary.INTEGER32: "l",
        objectdictionary.UNSIGNED8: "B",
        objectdictionary.UNSIGNED16: "H",
        objectdictionary.UNSIGNED32: "L",
        objectdictionary.REAL32: "f"
    }

    def __init__(self, node, od_par):
        self.node = node
        self.od = od_par
        self.subindex = self.od.subindex

    @property
    def raw(self):
        """Get raw value of parameter (SDO upload)"""
        logging.info("Reading %s.%s (0x%X:%d) from node %d",
            self.od.parent.name, self.od.name, self.od.parent.index,
            self.subindex, self.node.node_id)

        sdo_request = SDO_STRUCT.pack(0x40,
                                      self.od.parent.index,
                                      self.subindex,
                                      0)

        msg = self.node.query(sdo_request)
        command, index, subindex, value = SDO_STRUCT.unpack(msg)

        if command == 0x41:
            # Segmented transfer
            length = value
            logging.debug("Starting segmented transfer for %d bytes", length)
            data = bytearray(length)
            sdo_request = bytearray(8)
            sdo_request[0] = 0x60

            for pos in range(0, length, 7):
                msg = self.parent.node.sdo_query(sdo_request)
                data[pos:pos+7] = msg[1:8]

                # Toggle bit
                sdo_request[0] ^= 0x10

            del data[length:]
        else:
            # Expedited transfer
            data = msg[4:8]

        if self.od.data_type == objectdictionary.VIS_STR:
            value = data.decode("ascii")
        else:
            fmt = "<" + self.DATA_TYPES[self.od.data_type]
            value, = struct.unpack_from(fmt, data)

        return value

    @raw.setter
    def raw(self, value):
        """Write raw value to parameter (SDO download)"""
        logging.info("Writing %s.%s (0x%X:%d) = %s to node %d",
            self.od.parent.name, self.od.name, self.od.parent.index,
            self.subindex, value, self.node.node_id)

        if self.od.data_type == objectdictionary.VIS_STR:
            # Segmented transfer
            data = value.encode("ascii")
            length = len(data)

            sdo_request = SDO_STRUCT.pack(0x21,
                                          self.od.parent.index,
                                          self.subindex,
                                          length)
            logging.debug("Starting segmented transfer for %d bytes", length)
            self.node.sdo_query(sdo_request)

            # Start transmission of segments
            sdo_request = bytearray(8)
            for pos in range(0, length, 7):
                sdo_request[1:8] = data[pos:pos+7]
                if pos+7 >= length:
                    sdo_request[0] |= 1
                    # Make sure DLC is 8
                    sdo_request = sdo_request.ljust(8, b"\x00")
                self.node.sdo_query(sdo_request)

                # Toggle bit
                sdo_request[0] ^= 0x10
        else:
            # Expedited transfer
            if (self.od.data_type == objectdictionary.INTEGER8 or
                self.od.data_type == objectdictionary.UNSIGNED8):
                command = 0x2F
            elif (self.od.data_type == objectdictionary.INTEGER16 or
                  self.od.data_type == objectdictionary.UNSIGNED16):
                command = 0x2B
            else:
                command = 0x23

            sdo_request = bytearray(8)
            fmt = "<BHB" + self.DATA_TYPES[self.od.data_type]
            struct.pack_into(fmt, sdo_request, 0, command,
                             self.od.parent.index,
                             self.subindex, int(value))

            self.node.query(sdo_request)

        logging.debug("Node accepted")

    @property
    def phys(self):
        value = self.raw

        try:
            value *= self.od.factor
            value += self.od.offset
        except TypeError:
            pass

        return value

    @phys.setter
    def phys(self, value):
        try:
            value -= self.od.offset
            value /= self.od.factor
            value = int(round(value))
        except TypeError:
            pass

        self.raw = value

    @property
    def desc(self):
        value = self.raw

        if not self.value_descriptions:
            raise Exception("No value descriptions exist")
        elif value not in self.value_descriptions:
            raise Exception("No value description exists for %d" % value)
        else:
            return self.value_descriptions[value]

    @desc.setter
    def desc(self, desc):
        if not self.value_descriptions:
            raise Exception("No value descriptions exist")
        else:
            for value, description in self.value_descriptions.items():
                if description == desc:
                    self.raw = value
                    return
        valid_values = ", ".join(self.value_descriptions.values())
        error_text = "No value corresponds to '%s'. Valid values are: %s"
        raise Exception(error_text % (desc, valid_values))


class SdoAbortedError(Exception):
    """SDO abort exception."""

    CODES = {
        0x05040000: "Timeout of transfer communication detected",
        0x06010000: "Unsupported access to an object",
        0x06010001: "Attempt to read a write only object",
        0x06010002: "Attempt to write a read only object",
        0x06060000: "Access failed due to a hardware error",
        0x06090030: "Value range of parameter exceeded",
        0x08000021: ("Data can not be transferred or stored to the application "
                     "because of local control"),
        0x08000022: ("Data can not be transferred or stored to the application "
                     "because of the present device state")
    }

    def __init__(self, code):
        self.code = code
        super(SdoAbortedError, self).__init__()

    def __str__(self):
        try:
            return self.CODES[self.code]
        except KeyError:
            return "SDO was aborted with code 0x{:08X}".format(self.code)


class SdoCommunicationError(Exception):
    pass
