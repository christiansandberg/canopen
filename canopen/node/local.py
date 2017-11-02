from .base import BaseNode
from ..sdo import SdoServer


class LocalNode(BaseNode):

    def __init__(self, node_id, object_dictionary):
        super(LocalNode, self).__init__(node_id, object_dictionary)

        self.data_store = {}
        self.callbacks = []

        self.sdo = SdoServer(0x600 + self.id, 0x580 + self.id, self)

    def associate_network(self, network):
        self.network = network
        self.sdo.network = network
        network.subscribe(self.sdo.rx_cobid, self.sdo.on_request)

    def remove_network(self):
        self.network.unsubscribe(self.sdo.rx_cobid)
        self.network = None
        self.sdo.network = None

    def add_callback(self, callback):
        self.callbacks.append(callback)
