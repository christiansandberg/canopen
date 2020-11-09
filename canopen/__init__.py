from pkg_resources import get_distribution, DistributionNotFound
from .network import Network, NodeScanner
from .node import RemoteNode, LocalNode
from .sdo import SdoCommunicationError, SdoAbortedError
from .objectdictionary import import_od, ObjectDictionary, ObjectDictionaryError
from .profiles.p402 import BaseNode402

Node = RemoteNode

try:
    __version__ = get_distribution(__name__).version
except DistributionNotFound:
    # package is not installed
    __version__ = "unknown"

__pypi_url__ = "https://pypi.org/project/canopen/"
