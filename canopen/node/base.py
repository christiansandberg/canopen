from typing import Optional, TYPE_CHECKING
from abc import ABC, abstractmethod

from canopen import objectdictionary
from canopen.objectdictionary import ObjectDictionary, TObjectDictionary

if TYPE_CHECKING:
    from canopen.network import Network
    from canopen.sdo.base import SdoBase
    from canopen.nmt import NmtBase
    from canopen.emcy import EmcyBase
    from canopen.pdo import TPDO, RPDO


class BaseNode(ABC):
    """A CANopen node.

    :param node_id:
        Node ID (set to None or 0 if specified by object dictionary)
    :param object_dictionary:
        Object dictionary as either a path to a file, an ``ObjectDictionary``
        or a file like object.
    """

    # Attribute types
    network: Optional["Network"]
    object_dictionary: ObjectDictionary
    id: int

    sdo: "SdoBase"
    tpdo: "TPDO"
    rpdo: "RPDO"
    nmt: "NmtBase"
    emcy: "EmcyBase"

    def __init__(
        self,
        node_id: Optional[int],
        object_dictionary: TObjectDictionary,
    ):
        self.network = None

        self.object_dictionary = objectdictionary.import_od(
                object_dictionary, node_id)

        # The rest of the Node class depend on a numeric ID, so unless
        # the OD provides one, return an error
        _node_id = node_id or self.object_dictionary.node_id
        if _node_id is None:
            raise RuntimeError("Missing node id for node")
        self.id = _node_id

    @abstractmethod
    def associate_network(self, network: "Network"):
        raise RuntimeError("Not implemented")

    @abstractmethod
    def remove_network(self):
        raise RuntimeError("Not implemented")
