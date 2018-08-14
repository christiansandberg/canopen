import logging
from .base import PdoBase, Maps



logger = logging.getLogger(__name__)

"""PDO Transmission types.
For more information please refer to http://www.canopensolutions.com/english/about_canopen/pdo.shtml"""
PTT={
    # TPDO
    'SYNCACYCLIC' : 0x00,
    #SYNCCYLIC = 0x1 to 0xF0 (depends on the number of sync's)
    #RESERVED = 0xF1 to 0xFB
    'SYNCRTRONLY' : 0xFC,
    'ASYNCRTRONLY' : 0xFD,
    'EVENTDRIVEN' : 0xFF,
    
    # RPDO
    'SYNC' : 0x0,
    'ASYNC' : 0xFF,
}
    


class TPDO(PdoBase):
    """PDO specialization for the Transmit PDO enabling the transfer of data from the node to the master.
    Properties 0x1800 to 0x1803 | Mapping 0x1600 to 0x1603."""
    
    
    def __init__(self, node):
        super(TPDO, self).__init__(node)
        self.map = Maps(0x1800, 0x1A00, self, 0x180)
        self.subscribers = {}
        
        # DEBUG
        print 'Lenght: {0}'.format(len(self.map))
    
        
    def on_sync(self, can_id, data, timestamp):
        pass
    
    
    def on_data_change(self):
        pass