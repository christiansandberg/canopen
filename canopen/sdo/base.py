import collections


class SdoBase(collections.Mapping):

    def __init__(self, rx_cobid, tx_cobid, od):
        """
        :param int rx_cobid:
            COB-ID that the server receives on (usually 0x600 + node ID)
        :param int tx_cobid:
            COB-ID that the server responds with (usually 0x580 + node ID)
        :param canopen.ObjectDictionary od:
            Object Dictionary to use for communication
        """
        self.rx_cobid = rx_cobid
        self.tx_cobid = tx_cobid
        self.network = None
        self.od = od

    def __getitem__(self, index):
        return self.od[index]

    def __iter__(self):
        return iter(self.od)

    def __len__(self):
        return len(self.od)

    def __contains__(self, key):
        return key in self.od
