from __future__ import annotations
from typing import TextIO, Union, Optional, TYPE_CHECKING
from .. import objectdictionary

if TYPE_CHECKING:
    from ..network import Network


class BaseNode:
    """A CANopen node.

    :param node_id:
        Node ID (set to None or 0 if specified by object dictionary)
    :param object_dictionary:
        Object dictionary as either a path to a file, an ``ObjectDictionary``
        or a file like object.
    """

    def __init__(
        self,
        node_id: Optional[int],
        object_dictionary: Union[objectdictionary.ObjectDictionary, str, TextIO],
    ):
        self.network: Optional[Network] = None

        if not isinstance(object_dictionary,
                          objectdictionary.ObjectDictionary):
            object_dictionary = objectdictionary.import_od(
                object_dictionary, node_id)
        self.object_dictionary = object_dictionary

        self.id = node_id or self.object_dictionary.node_id
