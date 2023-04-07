"""
Object Dictionary module
"""
from typing import Dict, Iterator, List, Optional, Set, TextIO, Union, TYPE_CHECKING, cast
import struct
import logging

try:
    from collections.abc import MutableMapping, Mapping
except ImportError:
    from collections import MutableMapping, Mapping  # type: ignore

from .datatypes import *

if TYPE_CHECKING:
    # Repeat import to ensure the type checker understands the imports
    from collections.abc import MutableMapping, Mapping

# FIXME: Make better naming for these
TObject = Union["Array", "Record", "Variable"]
TParent = Union[TObject, "ObjectDictionary"]
TValue = Union[int, float, str, bytes, bytearray]
TPhys = Union[int, float, bool, str, bytes]
TRaw = Union[int, float, bool, str, bytes]
TObjectDictionary = Union[str, "ObjectDictionary", TextIO, None]

logger = logging.getLogger(__name__)


def export_od(od: "ObjectDictionary", dest: Union[str, TextIO, None] = None,
              doc_type:Optional[str] = None):
    """ Export :class: ObjectDictionary to a file.

    :param od:
        :class: ObjectDictionary object to be exported
    :param dest:
        export destination. filename, or file-like object or None.
        if None, the document is returned as string
    :param doc_type: type of document to export.
       If a filename is given for dest, this default to the file extension.
       Otherwise, this defaults to "eds"
    :rtype: str or None
    """

    doctypes = {"eds", "dcf"}
    if isinstance(dest, str):
        if doc_type is None:
            for t in doctypes:
                if dest.endswith(f".{t}"):
                    doc_type = t
                    break

        if doc_type is None:
            doc_type = "eds"
        dest = open(dest, 'w')
    assert doc_type in doctypes

    if doc_type == "eds":
        from . import eds
        return eds.export_eds(od, dest)
    elif doc_type == "dcf":
        from . import eds
        return eds.export_dcf(od, dest)

    # If dest is opened in this fn, it should be closed
    if isinstance(dest, str):
        dest.close()


def import_od(
    source: TObjectDictionary,
    node_id: Optional[int] = None,
) -> "ObjectDictionary":
    """Parse an EDS, DCF, or EPF file.

    :param source:
        Path to object dictionary file or a file like object or an EPF XML tree.

    :return:
        An Object Dictionary instance.
    """
    if source is None:
        return ObjectDictionary()
    if isinstance(source, ObjectDictionary):
        return source
    if hasattr(source, "read"):
        # File like object -- Python file handles are a bit weird, so the cast
        # is needed to help the type checker
        filename = cast(TextIO, source).name
    elif hasattr(source, "tag"):
        # XML tree, probably from an EPF file
        filename = "od.epf"
    else:
        # Path to file
        filename = cast(str, source)
    suffix = filename[filename.rfind("."):].lower()
    if suffix in (".eds", ".dcf"):
        from . import eds
        return eds.import_eds(source, node_id)
    elif suffix == ".epf":
        from . import epf
        return epf.import_epf(source)
    else:
        raise NotImplementedError("No support for this format")


class ObjectDictionary(MutableMapping[Union[str, int], TObject]):
    """Representation of the object dictionary as a Python dictionary."""

    # Attribute types
    indices: Dict[int, TObject]
    names: Dict[str, TObject]
    comments: str
    bitrate: Optional[int]
    node_id: Optional[int]
    device_information: "DeviceInformation"

    def __init__(self):
        self.indices = {}
        self.names = {}
        self.comments = ""
        #: Default bitrate if specified by file
        self.bitrate = None
        #: Node ID if specified by file
        self.node_id = None
        #: Some information about the device
        self.device_information = DeviceInformation()

    def __getitem__(self, index: Union[int, str]
                   ) -> Union["Array", "Record", "Variable"]:
        """Get object from object dictionary by name or index."""
        item: Optional[TObject]
        item = self.names.get(index) or self.indices.get(index)  # type: ignore
        if item is None:
            name = "0x%X" % index if isinstance(index, int) else index
            raise KeyError("%s was not found in Object Dictionary" % name)
        return item

    def __setitem__(self, index: Union[int, str], obj: TObject):
        assert index == obj.index or index == obj.name
        self.add_object(obj)

    def __delitem__(self, index: Union[int, str]):
        obj = self[index]
        del self.indices[obj.index]
        del self.names[obj.name]

    def __iter__(self) -> Iterator[int]:
        return iter(sorted(self.indices))

    def __len__(self) -> int:
        return len(self.indices)

    def __contains__(self, index):
        return index in self.names or index in self.indices

    def add_object(self, obj: TObject) -> None:
        """Add object to the object dictionary.

        :param obj:
            Should be either one of
            :class:`~canopen.objectdictionary.Variable`,
            :class:`~canopen.objectdictionary.Record`, or
            :class:`~canopen.objectdictionary.Array`.
        """
        obj.parent = self
        self.indices[obj.index] = obj
        self.names[obj.name] = obj

    def get_variable(
        self, index: Union[int, str], subindex: int = 0
    ) -> Optional["Variable"]:
        """Get the variable object at specified index (and subindex if applicable).

        :return: Variable if found, else `None`
        """
        obj = self.get(index)
        if isinstance(obj, Variable):
            return obj
        elif isinstance(obj, (Record, Array)):
            return obj.get(subindex)
        return None


class Record(MutableMapping[Union[int, str], "Variable"]):
    """Groups multiple :class:`~canopen.objectdictionary.Variable` objects using
    subindices.
    """

    # Attribute types
    parent: Optional[TParent]
    index: int
    name: str
    storage_location: Optional[str]
    subindices: Dict[int, "Variable"]
    names: Dict[str, "Variable"]
    description: str

    def __init__(self, name: str, index: int):
        #: The :class:`~canopen.ObjectDictionary` owning the record.
        self.parent = None
        #: 16-bit address of the record
        self.index = index
        #: Name of record
        self.name = name
        #: Storage location of index
        self.storage_location = None
        self.subindices = {}
        self.names = {}
        #: Description for the whole record
        self.description = ""

    def __getitem__(self, subindex: Union[int, str]) -> "Variable":
        item = self.names.get(subindex) or self.subindices.get(subindex)  # type: ignore
        if item is None:
            raise KeyError("Subindex %s was not found" % subindex)
        return item

    def __setitem__(self, subindex: Union[int, str], var: "Variable"):
        assert subindex == var.subindex
        self.add_member(var)

    def __delitem__(self, subindex: Union[int, str]):
        var = self[subindex]
        del self.subindices[var.subindex]
        del self.names[var.name]

    def __len__(self) -> int:
        return len(self.subindices)

    def __iter__(self) -> Iterator[int]:
        return iter(sorted(self.subindices))

    def __contains__(self, subindex) -> bool:
        return subindex in self.names or subindex in self.subindices

    def __eq__(self, other) -> bool:
        if not isinstance(other, Record):
            raise NotImplementedError()
        return self.index == other.index

    def add_member(self, variable: "Variable") -> None:
        """Adds a :class:`~canopen.objectdictionary.Variable` to the record."""
        variable.parent = self
        self.subindices[variable.subindex] = variable
        self.names[variable.name] = variable


class Array(Mapping[Union[int, str], "Variable"]):
    """An array of :class:`~canopen.objectdictionary.Variable` objects using
    subindices.

    Actual length of array must be read from the node using SDO.
    """

    # Attribute types
    parent: Optional[TParent]
    index: int
    name: str
    storage_location: Optional[str]
    subindices: Dict[int, "Variable"]
    names: Dict[str, "Variable"]
    description: str

    def __init__(self, name: str, index: int):
        #: The :class:`~canopen.ObjectDictionary` owning the record.
        self.parent = None
        #: 16-bit address of the array
        self.index = index
        #: Name of array
        self.name = name
        #: Storage location of index
        self.storage_location = None
        self.subindices = {}
        self.names = {}
        #: Description for the whole array
        self.description = ""

    def __getitem__(self, subindex: Union[int, str]) -> "Variable":
        var = self.names.get(subindex) or self.subindices.get(subindex)  # type: ignore
        if var is not None:
            # This subindex is defined
            pass
        elif isinstance(subindex, int) and 0 < subindex < 256:
            # Create a new variable based on first array item
            template = self.subindices[1]
            name = "%s_%x" % (template.name, subindex)
            var = Variable(name, self.index, subindex)
            var.parent = self
            for attr in ("data_type", "unit", "factor", "min", "max", "default",
                         "access_type", "description", "value_descriptions",
                         "bit_definitions", "storage_location"):
                if attr in template.__dict__:
                    var.__dict__[attr] = template.__dict__[attr]
        else:
            raise KeyError("Could not find subindex %r" % subindex)
        return var

    def __len__(self) -> int:
        return len(self.subindices)

    def __iter__(self) -> Iterator[int]:
        return iter(sorted(self.subindices))

    def __eq__(self, other) -> bool:
        if not isinstance(other, Array):
            raise NotImplementedError()
        return self.index == other.index

    def add_member(self, variable: "Variable") -> None:
        """Adds a :class:`~canopen.objectdictionary.Variable` to the record."""
        variable.parent = self
        self.subindices[variable.subindex] = variable
        self.names[variable.name] = variable


class Variable:
    """Simple variable."""

    STRUCT_TYPES = {
        BOOLEAN:    struct.Struct("?"),   # bool
        INTEGER8:   struct.Struct("b"),   # int
        INTEGER16:  struct.Struct("<h"),  # int
        INTEGER32:  struct.Struct("<l"),  # int
        INTEGER64:  struct.Struct("<q"),  # int
        UNSIGNED8:  struct.Struct("B"),   # int
        UNSIGNED16: struct.Struct("<H"),  # int
        UNSIGNED32: struct.Struct("<L"),  # int
        UNSIGNED64: struct.Struct("<Q"),  # int
        REAL32:     struct.Struct("<f"),  # float
        REAL64:     struct.Struct("<d"),  # float
    }

    def __init__(self, name: str, index: int, subindex: int = 0):
        #: The :class:`~canopen.ObjectDictionary`,
        #: :class:`~canopen.objectdictionary.Record` or
        #: :class:`~canopen.objectdictionary.Array` owning the variable
        self.parent: Optional[TParent] = None
        #: 16-bit address of the object in the dictionary
        self.index: int = index
        #: 8-bit sub-index of the object in the dictionary
        self.subindex: int = subindex
        #: String representation of the variable
        self.name: str = name
        #: Physical unit
        self.unit: str = ""
        #: Factor between physical unit and integer value
        self.factor: float = 1
        #: Minimum allowed value
        self.min: Optional[int] = None
        #: Maximum allowed value
        self.max: Optional[int] = None
        #: Default value at start-up
        self.default: Optional[TRaw] = None
        #: Is the default value relative to the node-ID (only applies to COB-IDs)
        self.relative: bool = False
        #: The value of this variable stored in the object dictionary
        self.value: Optional[TRaw] = None
        #: Data type according to the standard as an :class:`int`
        self.data_type: Optional[int] = None
        #: Access type, should be "rw", "ro", "wo", or "const"
        self.access_type: str = "rw"
        #: Description of variable
        self.description: str = ""
        #: Dictionary of value descriptions
        self.value_descriptions: Dict[int, str] = {}
        #: Dictionary of bitfield definitions
        self.bit_definitions: Dict[str, List[int]] = {}
        #: Storage location of index
        self.storage_location: Optional[str] = None
        #: Can this variable be mapped to a PDO
        self.pdo_mappable: bool = False


    def __eq__(self, other) -> bool:
        if not isinstance(other, Variable):
            raise NotImplementedError()
        return (self.index == other.index and
                self.subindex == other.subindex)

    def __len__(self) -> int:
        if self.data_type in self.STRUCT_TYPES:
            return self.STRUCT_TYPES[self.data_type].size * 8
        else:
            return 8

    @property
    def writable(self) -> bool:
        return "w" in self.access_type

    @property
    def readable(self) -> bool:
        return "r" in self.access_type or self.access_type == "const"

    def add_value_description(self, value: int, descr: str) -> None:
        """Associate a value with a string description.

        :param value: Value to describe
        :param desc: Description of value
        """
        self.value_descriptions[value] = descr

    def add_bit_definition(self, name: str, bits: List[int]) -> None:
        """Associate bit(s) with a string description.

        :param name: Name of bit(s)
        :param bits: List of bits as integers
        """
        self.bit_definitions[name] = bits

    def decode_raw(self, data: bytes) -> TRaw:
        if self.data_type == VISIBLE_STRING:
            # Return str
            return data.rstrip(b"\x00").decode("ascii", errors="ignore")
        elif self.data_type == UNICODE_STRING:
            # Returns str
            # Is this correct?
            return data.rstrip(b"\x00").decode("utf_16_le", errors="ignore")
        elif self.data_type in self.STRUCT_TYPES:
            try:
                # Returns one of bool, int, float
                value: Union[bool, int, float]
                value, = self.STRUCT_TYPES[self.data_type].unpack(data)
                return value
            except struct.error:
                raise ObjectDictionaryError(
                    "Mismatch between expected and actual data size")
        else:
            # Just return the data as is (type: bytes)
            return data

    # FIXME: Q: Keeping type of the dictionary object separate (self.data_type)
    #        from the actual type of value. How to deal with that?

    def encode_raw(self, value: TRaw) -> bytes:
        if isinstance(value, (bytes, bytearray)):
            # FIXME: Is this right? If the type is bytes then the self.data_type
            #        is not checked
            return value
        elif self.data_type == VISIBLE_STRING:
            if not isinstance(value, str):
                raise TypeError("Value of type '%s' doesn't match VISIBLE_STRING" % (
                    type(value)
                ))
            return value.encode("ascii")
        elif self.data_type == UNICODE_STRING:
            if not isinstance(value, str):
                raise TypeError("Value of type '%s' doesn't match UNICODE_STRING" % (
                    type(value)
                ))
            # Is this correct?
            return value.encode("utf_16_le")
        elif self.data_type in self.STRUCT_TYPES:
            if not isinstance(value, (bool, int, float)):
                raise TypeError("Value of type '%s' is unexpected for numeric types" % (
                    type(value)
                ))
            if self.data_type in INTEGER_TYPES:
                value = int(value)
            if self.data_type in NUMBER_TYPES:
                if self.min is not None and value < self.min:
                    logger.warning(
                        "Value %d is less than min value %d", value, self.min)
                if self.max is not None and value > self.max:
                    logger.warning(
                        "Value %d is greater than max value %d",
                        value,
                        self.max)
            try:
                return self.STRUCT_TYPES[self.data_type].pack(value)
            except struct.error:
                raise ValueError("Value does not fit in specified type")
        elif self.data_type is None:
            raise ObjectDictionaryError("Data type has not been specified")
        else:
            raise TypeError(
                "Do not know how to encode %r to data type %Xh" % (
                    value, self.data_type))

    # FIXME: Q: What is the correct type of .phys? Is it anything (depending
    #        on the type of the od), or should it be int?

    def decode_phys(self, value: TRaw) -> TPhys:
        if self.data_type in INTEGER_TYPES:
            # FIXME: Allow float?
            if not isinstance(value, (int, float)):
                raise TypeError("Value of type '%s' is unexpected for numeric types" % (
                    type(value)
                ))
            value *= self.factor
            # FIXME: Convert to int?
        return value

    def encode_phys(self, value: TPhys) -> TRaw:
        if self.data_type in INTEGER_TYPES:
            # FIXME: Allow float?
            if not isinstance(value, (int, float)):
                raise TypeError("Value of type '%s' is unexpected for numeric types" % (
                    type(value)
                ))
            value /= self.factor
            value = int(round(value))
        return value

    def decode_desc(self, value: int) -> str:
        if not self.value_descriptions:
            raise ObjectDictionaryError("No value descriptions exist")
        elif value not in self.value_descriptions:
            raise ObjectDictionaryError(
                "No value description exists for %d" % value)
        else:
            return self.value_descriptions[value]

    def encode_desc(self, desc: str) -> int:
        if not self.value_descriptions:
            raise ObjectDictionaryError("No value descriptions exist")
        else:
            for value, description in self.value_descriptions.items():
                if description == desc:
                    return value
        valid_values = ", ".join(self.value_descriptions.values())
        error_text = "No value corresponds to '%s'. Valid values are: %s"
        raise ValueError(error_text % (desc, valid_values))

    # FIXME: bits typing might be wrong here.
    def decode_bits(self, value: int, bits: List[int]) -> int:
        try:
            bits = self.bit_definitions[bits]
        except (TypeError, KeyError):
            pass
        mask = 0
        for bit in bits:
            mask |= 1 << bit
        return (value & mask) >> min(bits)

    # FIXME: bits typing might be wrong here.
    def encode_bits(self, original_value: int, bits: List[int], bit_value: int):
        try:
            bits = self.bit_definitions[bits]
        except (TypeError, KeyError):
            pass
        temp = original_value
        mask = 0
        for bit in bits:
            mask |= 1 << bit
        temp &= ~mask
        temp |= bit_value << min(bits)
        return temp


class DeviceInformation:
    def __init__(self):
        self.allowed_baudrates: Set[int] = set()
        self.vendor_name: Optional[str] = None
        self.vendor_number: Optional[int] = None
        self.product_name: Optional[str] = None
        self.product_number: Optional[int] = None
        self.revision_number: Optional[int] = None
        self.order_code: Optional[str] = None
        self.simple_boot_up_master: Optional[bool] = None
        self.simple_boot_up_slave: Optional[bool] = None
        self.granularity: Optional[int] = None
        self.dynamic_channels_supported: Optional[bool] = None
        self.group_messaging: Optional[bool] = None
        self.nr_of_RXPDO: Optional[bool] = None
        self.nr_of_TXPDO: Optional[bool] = None
        self.LSS_supported: Optional[bool] = None


class ObjectDictionaryError(Exception):
    """Unsupported operation with the current Object Dictionary."""
