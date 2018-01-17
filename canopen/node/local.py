import struct
from .base import BaseNode
from ..sdo import SdoServer
from ..nmt import NmtSlave


class LocalNode(BaseNode):

    def __init__(self, node_id, object_dictionary):
        super(LocalNode, self).__init__(node_id, object_dictionary)

        self.data_store = {}
        self.callbacks = []

        self.sdo = SdoServer(0x600 + self.id, 0x580 + self.id, self)
        self.nmt = NmtSlave(self.id)
        self.add_callback(self._producer_hearbeat_time_callback)

    def associate_network(self, network):
        self.network = network
        self.sdo.network = network
        self.nmt.network = network
        network.subscribe(self.sdo.rx_cobid, self.sdo.on_request)

    def remove_network(self):
        self.network.unsubscribe(self.sdo.rx_cobid)
        self.network = None
        self.sdo.network = None
        self.nmt.network = None

    def add_callback(self, callback):
        self.callbacks.append(callback)

    def _producer_hearbeat_time_callback(self, **kwargs):
        if kwargs["index"] == 0x1017:
            if kwargs["data"] is None:
                # This is a read callback. If we return none
                # the data will be read from local storage
                return None
            elif kwargs["data"] == 0:
                self.nmt.stop_heartbeat()
            else:
                (hearbeat_time, ) = struct.unpack_from("<H", kwargs["data"])
                self.nmt.start_heartbeat(hearbeat_time)
            return 0x0201
