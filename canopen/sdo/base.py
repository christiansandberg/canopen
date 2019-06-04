import binascii
try:
    from collections.abc import Mapping
except ImportError:
    from collections import Mapping

from .. import objectdictionary
from .. import variable


class CrcXmodem(object):
    """Mimics CrcXmodem from crccheck."""

    def __init__(self):
        self._value = 0

    def process(self, data):
        self._value = binascii.crc_hqx(data, self._value)

    def final(self):
        return self._value


class SdoBase(Mapping):

    #: The CRC algorithm used for block transfers
    crc_cls = CrcXmodem

    def __init__(self, rx_cobid, tx_cobid, od):
        """
        :param int rx_cobid:
            COB-ID that the server receives on (usually 0x600 + node ID)
        :param int tx_cobid:
            COB-ID that the server responds with (usually 0x580 + node ID)
        :param canopen.ObjectDictionary od:
            Object Dictionary to use for communication
        """
        self.rx_cobid = rx_cobid
        self.tx_cobid = tx_cobid
        self.network = None
        self.od = od

    def __getitem__(self, index):
        entry = self.od[index]
        if isinstance(entry, objectdictionary.Variable):
            return Variable(self, entry)
        elif isinstance(entry, objectdictionary.Array):
            return Array(self, entry)
        elif isinstance(entry, objectdictionary.Record):
            return Record(self, entry)

    def __iter__(self):
        return iter(self.od)

    def __len__(self):
        return len(self.od)

    def __contains__(self, key):
        return key in self.od


class Record(Mapping):

    def __init__(self, sdo_node, od):
        self.sdo_node = sdo_node
        self.od = od

    def __getitem__(self, subindex):
        return Variable(self.sdo_node, self.od[subindex])

    def __iter__(self):
        return iter(self.od)

    def __len__(self):
        return len(self.od)

    def __contains__(self, subindex):
        return subindex in self.od


class Array(Mapping):

    def __init__(self, sdo_node, od):
        self.sdo_node = sdo_node
        self.od = od

    def __getitem__(self, subindex):
        return Variable(self.sdo_node, self.od[subindex])

    def __iter__(self):
        return iter(range(1, len(self) + 1))

    def __len__(self):
        return self[0].raw

    def __contains__(self, subindex):
        return 0 <= subindex <= len(self)


class Variable(variable.Variable):
    """Access object dictionary variable values using SDO protocol."""

    def __init__(self, sdo_node, od):
        self.sdo_node = sdo_node
        variable.Variable.__init__(self, od)

    def get_data(self):
        return self.sdo_node.upload(self.od.index, self.od.subindex)

    def set_data(self, data):
        force_segment = self.od.data_type == objectdictionary.DOMAIN
        self.sdo_node.download(self.od.index, self.od.subindex, data, force_segment)

    def open(self, mode="rb", encoding="ascii", buffering=1024, size=None,
             block_transfer=False):
        """Open the data stream as a file like object.

        :param str mode:
            ========= ==========================================================
            Character Meaning
            --------- ----------------------------------------------------------
            'r'       open for reading (default)
            'w'       open for writing
            'b'       binary mode (default)
            't'       text mode
            ========= ==========================================================
        :param str encoding:
            The str name of the encoding used to decode or encode the file.
            This will only be used in text mode.
        :param int buffering:
            An optional integer used to set the buffering policy. Pass 0 to
            switch buffering off (only allowed in binary mode), 1 to select line
            buffering (only usable in text mode), and an integer > 1 to indicate
            the size in bytes of a fixed-size chunk buffer.
        :param int size:
            Size of data to that will be transmitted.
        :param bool block_transfer:
            If block transfer should be used.

        :returns:
            A file like object.
        """
        return self.sdo_node.open(self.od.index, self.od.subindex, mode,
                                  encoding, buffering, size, block_transfer)
