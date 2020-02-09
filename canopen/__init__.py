from .version import __version__
from .network import Network, NodeScanner
from .node import RemoteNode, LocalNode
from .sdo import SdoCommunicationError, SdoAbortedError
from .objectdictionary import import_od, ObjectDictionary, ObjectDictionaryError
from .profiles.p402 import BaseNode402

Node = RemoteNode

__all__ = [
    "__version__",
    "Network",
    "NodeScanner",
    "RemoteNode",
    "LocalNode",
    "SdoCommunicationError",
    "SdoAbortedError",
    "import_od",
    "ObjectDictionary",
    "ObjectDictionaryError",
    "BaseNode402",
]
