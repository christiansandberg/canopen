import logging

from ..sdo import SdoClient
from ..nmt import NmtMaster
from ..emcy import EmcyConsumer
from ..pdo import TPDO, RPDO, PDO
from ..objectdictionary import Record, Array, Variable
from .base import BaseNode

import canopen

logger = logging.getLogger(__name__)


class RemoteNode(BaseNode):
    """A CANopen remote node.

    :param int node_id:
        Node ID (set to None or 0 if specified by object dictionary)
    :param object_dictionary:
        Object dictionary as either a path to a file, an ``ObjectDictionary``
        or a file like object.
    :param bool load_od:
        Enable the Object Dictionary to be sent trought SDO's to the remote
        node at startup.
    :type object_dictionary: :class:`str`, :class:`canopen.ObjectDictionary`
    """

    def __init__(self, node_id, object_dictionary, load_od=False):
        super(RemoteNode, self).__init__(node_id, object_dictionary)

        #: Enable WORKAROUND for reversed PDO mapping entries
        self.curtis_hack = False

        self.sdo = SdoClient(0x600 + self.id, 0x580 + self.id,
                             self.object_dictionary)
        self.tpdo = TPDO(self)
        self.rpdo = RPDO(self)
        self.pdo = PDO(self, self.rpdo, self.tpdo)
        self.nmt = NmtMaster(self.id)
        self.emcy = EmcyConsumer()

        if load_od:
            self.load_configuration()

    def associate_network(self, network):
        self.network = network
        self.sdo.network = network
        self.pdo.network = network
        self.tpdo.network = network
        self.rpdo.network = network
        self.nmt.network = network
        network.subscribe(self.sdo.tx_cobid, self.sdo.on_response)
        network.subscribe(0x700 + self.id, self.nmt.on_heartbeat)
        network.subscribe(0x80 + self.id, self.emcy.on_emcy)
        network.subscribe(0, self.nmt.on_command)

    def remove_network(self):
        self.network.unsubscribe(self.sdo.tx_cobid, self.sdo.on_response)
        self.network.unsubscribe(0x700 + self.id, self.nmt.on_heartbeat)
        self.network.unsubscribe(0x80 + self.id, self.emcy.on_emcy)
        self.network.unsubscribe(0, self.nmt.on_command)
        self.network = None
        self.sdo.network = None
        self.pdo.network = None
        self.tpdo.network = None
        self.rpdo.network = None
        self.nmt.network = None

    def store(self, subindex=1):
        """Store parameters in non-volatile memory.

        :param int subindex:
            1 = All parameters\n
            2 = Communication related parameters\n
            3 = Application related parameters\n
            4 - 127 = Manufacturer specific
        """
        self.sdo.download(0x1010, subindex, b"save")

    def restore(self, subindex=1):
        """Restore default parameters.

        :param int subindex:
            1 = All parameters\n
            2 = Communication related parameters\n
            3 = Application related parameters\n
            4 - 127 = Manufacturer specific
        """
        self.sdo.download(0x1011, subindex, b"load")

    def load_configuration(self):
        ''' Load the configuration of the node from the object dictionary.'''
        for obj in self.object_dictionary.values():
            if isinstance(obj, Record) or isinstance(obj, Array):
                for subobj in obj.values():
                    if isinstance(subobj, Variable) and (subobj.access_type == 'rw') and (subobj.value is not None) :
                        logger.debug(str('SDO [{index}][{subindex}]: {name}: {value}'.format(
                            index=subobj.index,
                            subindex=subobj.subindex,
                            name=subobj.name,
                            value=subobj.value)))
                        try:
                            self.sdo[subobj.index][subobj.subindex].raw = subobj.value
                        except canopen.SdoCommunicationError as e:
                            logger.info(str(e))
                        except canopen.SdoAbortedError as e:
                            # WORKAROUND for broken implementations: the SDO is set but the error
                            # "Attempt to write a read-only object" is raised any way.
                            if e.code != 0x06010002:
                                # Abort codes other than "Attempt to write a read-only object"
                                # should still be reported.
                                print('[ERROR SETTING object {0}:{1}]  {2}'.format(subobj.index, subobj.subindex, str(e)))
                                logger.info(str(e))
                                raise
