from __future__ import annotations

import binascii
from collections.abc import Mapping
from typing import Iterator, Optional, Union

import canopen.network
from canopen import objectdictionary
from canopen import variable
from canopen.utils import pretty_index


class CrcXmodem:
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

    def __init__(
        self,
        rx_cobid: int,
        tx_cobid: int,
        od: objectdictionary.ObjectDictionary,
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
        self.network: canopen.network.Network = canopen.network._UNINITIALIZED_NETWORK
        self.od = od

    def __getitem__(
        self, index: Union[str, int]
    ) -> Union[SdoVariable, SdoArray, SdoRecord]:
        entry = self.od[index]
        if isinstance(entry, objectdictionary.ODVariable):
            return SdoVariable(self, entry)
        elif isinstance(entry, objectdictionary.ODArray):
            return SdoArray(self, entry)
        elif isinstance(entry, objectdictionary.ODRecord):
            return SdoRecord(self, entry)

    def __iter__(self) -> Iterator[int]:
        return iter(self.od)

    def __len__(self) -> int:
        return len(self.od)

    def __contains__(self, key: Union[int, str]) -> bool:
        return key in self.od

    def get_variable(
        self, index: Union[int, str], subindex: int = 0
    ) -> Optional[SdoVariable]:
        """Get the variable object at specified index (and subindex if applicable).

        :return: SdoVariable if found, else `None`
        """
        obj = self.get(index)
        if isinstance(obj, SdoVariable):
            return obj
        elif isinstance(obj, (SdoRecord, SdoArray)):
            return obj.get(subindex)

    def upload(self, index: int, subindex: int) -> bytes:
        raise NotImplementedError()

    async def aupload(self, index: int, subindex: int) -> bytes:
        raise NotImplementedError()

    def download(
        self,
        index: int,
        subindex: int,
        data: bytes,
        force_segment: bool = False,
    ) -> None:
        raise NotImplementedError()

    async def adownload(
        self,
        index: int,
        subindex: int,
        data: bytes,
        force_segment: bool = False,
    ) -> None:
        raise NotImplementedError()


class SdoRecord(Mapping):

    def __init__(self, sdo_node: SdoBase, od: objectdictionary.ODRecord):
        self.sdo_node = sdo_node
        self.od = od

    def __repr__(self) -> str:
        return f"<{type(self).__qualname__} {self.od.name!r} at {pretty_index(self.od.index)}>"

    def __getitem__(self, subindex: Union[int, str]) -> SdoVariable:
        return SdoVariable(self.sdo_node, self.od[subindex])

    def __iter__(self) -> Iterator[int]:
        # Skip the "highest subindex" entry, which is not part of the data
        return filter(None, iter(self.od))

    async def aiter(self):
        for i in iter(self.od):
            yield i

    def __aiter__(self):
        return self.aiter()

    def __len__(self) -> int:
        # Skip the "highest subindex" entry, which is not part of the data
        return len(self.od) - int(0 in self.od)

    async def alen(self) -> int:
        return len(self.od)

    def __contains__(self, subindex: Union[int, str]) -> bool:
        return subindex in self.od


class SdoArray(Mapping):

    def __init__(self, sdo_node: SdoBase, od: objectdictionary.ODArray):
        self.sdo_node = sdo_node
        self.od = od

    def __repr__(self) -> str:
        return f"<{type(self).__qualname__} {self.od.name!r} at {pretty_index(self.od.index)}>"

    def __getitem__(self, subindex: Union[int, str]) -> SdoVariable:
        return SdoVariable(self.sdo_node, self.od[subindex])

    def __iter__(self) -> Iterator[int]:
        # Skip the "highest subindex" entry, which is not part of the data
        return iter(range(1, len(self) + 1))

    async def aiter(self):
        for i in range(1, await self.alen() + 1):
            yield i

    def __aiter__(self):
        return self.aiter()

    def __len__(self) -> int:
        # NOTE: Blocking - OK. Protected in SdoClient
        return self[0].raw

    async def alen(self) -> int:
        return await self[0].aget_raw()

    def __contains__(self, subindex: int) -> bool:
        return 0 <= subindex <= len(self)


class SdoVariable(variable.Variable):
    """Access object dictionary variable values using SDO protocol."""

    def __init__(self, sdo_node: SdoBase, od: objectdictionary.ODVariable):
        self.sdo_node = sdo_node
        variable.Variable.__init__(self, od)

    def __await__(self):
        return self.aget_raw().__await__()

    def get_data(self) -> bytes:
        return self.sdo_node.upload(self.od.index, self.od.subindex)

    async def aget_data(self) -> bytes:
        return await self.sdo_node.aupload(self.od.index, self.od.subindex)

    def set_data(self, data: bytes):
        force_segment = self.od.data_type == objectdictionary.DOMAIN
        self.sdo_node.download(self.od.index, self.od.subindex, data, force_segment)

    async def aset_data(self, data: bytes):
        force_segment = self.od.data_type == objectdictionary.DOMAIN
        await self.sdo_node.adownload(self.od.index, self.od.subindex, data, force_segment)

    @property
    def writable(self) -> bool:
        return self.od.writable

    @property
    def readable(self) -> bool:
        return self.od.readable

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

    async def aopen(self, mode="rb", encoding="ascii", buffering=1024, size=None,
                    block_transfer=False, request_crc_support=True):
        """Open the data stream as a file like object. See open()"""
        return await self.sdo_node.aopen(self.od.index, self.od.subindex, mode,
                                         encoding, buffering, size, block_transfer,
                                         request_crc_support=request_crc_support)


# For compatibility
Record = SdoRecord
Array = SdoArray
Variable = SdoVariable
