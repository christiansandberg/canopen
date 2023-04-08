from typing import IO, Any, Iterator, Self, Union, Optional, TYPE_CHECKING
import binascii
import io
try:
    from collections.abc import Mapping
except ImportError:
    from collections import Mapping  # type: ignore

from canopen.objectdictionary import ObjectDictionary
from canopen import objectdictionary
from canopen import variable

if TYPE_CHECKING:
    # Repeat import to ensure the type checker understands the imports
    from collections.abc import Mapping
    from canopen.network import Network


class CrcXmodem:
    """Mimics CrcXmodem from crccheck."""

    # Attribute types
    _value: int

    def __init__(self):
        self._value = 0

    def process(self, data):
        self._value = binascii.crc_hqx(data, self._value)

    def final(self):
        return self._value


class SdoIO(io.RawIOBase, IO):

    size: Optional[int]

    def read(self, size: int = -1) -> bytes:
        return b''

    # For typing
    def __enter__(self) -> Self:
        return self

    # For typing
    def write(self, s: Any) -> int:
        raise Exception()


class SdoBase(Mapping[Union[str, int], Union["Variable", "Array", "Record"]]):

    # Attribute types
    network: Optional["Network"]
    od: ObjectDictionary
    rx_cobid: int
    tx_cobid: int

    #: The CRC algorithm used for block transfers
    crc_cls = CrcXmodem

    def __init__(
        self,
        rx_cobid: int,
        tx_cobid: int,
        od: ObjectDictionary,
    ):
        """
        :param rx_cobid:
            COB-ID that the server receives on (usually 0x600 + node ID)
        :param tx_cobid:
            COB-ID that the server responds with (usually 0x580 + node ID)
        :param od:
            Object Dictionary to use for communication
        """
        self.rx_cobid = rx_cobid
        self.tx_cobid = tx_cobid
        self.network: Optional[Network] = None
        self.od = od

    def __getitem__(
        self, index: Union[str, int]
    ) -> Union["Variable", "Array", "Record"]:
        entry = self.od[index]
        if isinstance(entry, objectdictionary.Variable):
            return Variable(self, entry)
        elif isinstance(entry, objectdictionary.Array):
            return Array(self, entry)
        elif isinstance(entry, objectdictionary.Record):
            return Record(self, entry)
        raise TypeError("Unknown object type")

    def __iter__(self) -> Iterator[int]:
        return iter(self.od)

    def __len__(self) -> int:
        return len(self.od)

    def __contains__(self, key) -> bool:
        return key in self.od

    def upload(self, index: int, subindex: int) -> bytes:
        raise NotImplementedError()

    def download(
        self,
        index: int,
        subindex: int,
        data: bytes,
        force_segment: bool = False,
    ) -> None:
        raise NotImplementedError()

    def open(
        self,
        index: int,
        subindex: int = 0,
        mode: str = "rb",
        encoding: str = "ascii",
        buffering: int = 1024,
        size=None,
        block_transfer=False,
        force_segment=False,
        request_crc_support=True
    ) -> Union[IO, SdoIO]:
        raise NotImplementedError()


class Record(Mapping[Union[int, str], "Variable"]):

    # Attribute types
    sdo_node: SdoBase
    od: objectdictionary.Record

    def __init__(self, sdo_node: SdoBase, od: objectdictionary.Record):
        self.sdo_node = sdo_node
        self.od = od

    def __getitem__(self, subindex: Union[int, str]) -> "Variable":
        return Variable(self.sdo_node, self.od[subindex])

    def __iter__(self) -> Iterator[int]:
        return iter(self.od)

    def __len__(self) -> int:
        return len(self.od)

    def __contains__(self, subindex) -> bool:
        return subindex in self.od


class Array(Mapping[Union[int, str], "Variable"]):

    # Attribute types
    sdo_node: SdoBase
    od: objectdictionary.Array

    def __init__(self, sdo_node: SdoBase, od: objectdictionary.Array):
        self.sdo_node = sdo_node
        self.od = od

    def __getitem__(self, subindex: Union[int, str]) -> "Variable":
        return Variable(self.sdo_node, self.od[subindex])

    def __iter__(self) -> Iterator[int]:
        return iter(range(1, len(self) + 1))

    def __len__(self) -> int:
        # FIXME: Is it an assumption that index 0 is int? Should it fail?
        return self[0].raw  # type: ignore

    def __contains__(self, subindex) -> bool:
        return 0 <= subindex <= len(self)


class Variable(variable.Variable):
    """Access object dictionary variable values using SDO protocol."""

    # Attribute types
    sdo_node: SdoBase
    od: objectdictionary.Variable

    def __init__(self, sdo_node: SdoBase, od: objectdictionary.Variable):
        self.sdo_node = sdo_node
        variable.Variable.__init__(self, od)

    def get_data(self) -> bytes:
        return self.sdo_node.upload(self.od.index, self.od.subindex)

    def set_data(self, data: bytes):
        force_segment = self.od.data_type == objectdictionary.DOMAIN
        self.sdo_node.download(self.od.index, self.od.subindex, data, force_segment)

    def open(self, mode="rb", encoding="ascii", buffering=1024, size=None,
             block_transfer=False, request_crc_support=True):
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
        :param bool request_crc_support:
            If crc calculation should be requested when using block transfer

        :returns:
            A file like object.
        """
        return self.sdo_node.open(self.od.index, self.od.subindex, mode,
                                  encoding, buffering, size, block_transfer, request_crc_support=request_crc_support)
