from .. import objectdictionary


class BaseNode(object):
    """A CANopen node.

    :param int node_id:
        Node ID (set to None or 0 if specified by object dictionary)
    :param object_dictionary:
        Object dictionary as either a path to a file, an ``ObjectDictionary``
        or a file like object.
    :type object_dictionary: :class:`str`, :class:`canopen.ObjectDictionary`
    """

    """PDO Transmission types.
    For more information please refer to http://www.canopensolutions.com/english/about_canopen/pdo.shtml"""
    PTT = {
    # TPDO
    'SYNCACYCLIC' : 0x00,
    # SYNCCYLIC = 0x1 to 0xF0 (depends on the number of sync's)
    # RESERVED = 0xF1 to 0xFB
    'SYNCRTRONLY' : 0xFC,
    'ASYNCRTRONLY' : 0xFD,
    'EVENTDRIVEN' : 0xFF,

    # RPDO
    'SYNC' : 0x0,
    'ASYNC' : 0xFF,
    }

    def __init__(self, node_id, object_dictionary):
        self.network = None

        if not isinstance(object_dictionary,
                          objectdictionary.ObjectDictionary):
            object_dictionary = objectdictionary.import_od(
                object_dictionary, node_id)
        self.object_dictionary = object_dictionary

        self.id = node_id or self.object_dictionary.node_id
