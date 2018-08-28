import logging
from .base import PdoBase, Maps

logger = logging.getLogger(__name__)


class RPDO(PdoBase):
    """PDO specialization for the Receive PDO enabling the transfer of data from the master to the node.
    Properties 0x1400 to 0x1403 | Mapping 0x1A00 to 0x1A03.
    :param object node: Parent node for this object."""

    def __init__(self, node):
        super(RPDO, self).__init__(node)
        self.map = Maps(0x1400, 0x1600, self, 0x200)
        logger.debug('RPDO Map as {0}'.format(len(self.map)))

    def get_rpdo(self, index):
        """Get PDO object through index
        :param int index: Index of the PDO mapping to retrive.
        """
        return self.map[index]

    def get_rpdos(self):
        return self.map
