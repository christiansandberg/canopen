import logging
from .base import PdoBase, Maps

logger = logging.getLogger(__name__)

class RPDO(PdoBase):
    """PDO specialization for the Receive PDO enabling the transfer of data from the master to the node.
    Properties 0x1400 to 0x1403 | Mapping 0x1A00 to 0x1A03."""

    def __init__(self, node):
        super(RPDO, self).__init__(node)
        self.map = Maps(0x1400, 0x1600, self, 0x200)
        

        

    def setup(self):
        pass

    def stop(self):
        """Stop transmission of all RPDOs."""
        for pdo in self.pdo_map.values():
            pdo.stop()
            
    def get(self, index):
        return self.map[index]


    