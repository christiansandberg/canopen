from collections import defaultdict
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

    def __init__(self, node_id, object_dictionary):
        # The network instance this node belongs to
        self.network = None
        # The ID of the node which identifies it within the network
        self.id = node_id or self.object_dictionary.node_id
        if not isinstance(object_dictionary,
                          objectdictionary.ObjectDictionary):
            object_dictionary = objectdictionary.import_od(
                object_dictionary, node_id)
        # The object dictionary describes the node's behaviour and exposed data
        self.object_dictionary = object_dictionary
        # Holds the current snapshot of the "live" data of this node
        self.data_store = {}
        # Changing the values of entries in the object dictionary of a node
        # usually entails a change of behaviour. The traps are a mechanism to
        # invoke the behaviour changing functions
        self.data_store_traps = defaultdict(list)
