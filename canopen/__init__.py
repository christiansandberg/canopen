from .network import Network, NodeScanner
from .node import RemoteNode, LocalNode
from .sdo import SdoCommunicationError, SdoAbortedError
from .objectdictionary import import_od, export_od, ObjectDictionary, ObjectDictionaryError
from .profiles.p402 import BaseNode402
try:
    from ._version import version as __version__
except ImportError:
    # package is not installed
    __version__ = "unknown"

Node = RemoteNode

__pypi_url__ = "https://pypi.org/project/canopen/"
