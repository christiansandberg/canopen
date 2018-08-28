import logging
from .base import PdoBase, Maps

logger = logging.getLogger(__name__)


class TPDO(PdoBase):
    """PDO specialization for the Transmit PDO enabling the transfer of data from the node to the master.
    Properties 0x1800 to 0x1803 | Mapping 0x1600 to 0x1603."""

    def __init__(self, node):
        super(TPDO, self).__init__(node)
        self.map = Maps(0x1800, 0x1A00, self, 0x180)
        self.subscribers = {}
        logger.debug('TPDO Map as {0}'.format(len(self.map)))

    def stop(self):
        """Stop transmission of all TPDOs."""
        for pdo in self.map.values():
            pdo.stop()

