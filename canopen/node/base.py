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
        self.network = None

        if not isinstance(object_dictionary,
                          objectdictionary.ObjectDictionary):
            object_dictionary = objectdictionary.import_od(
                object_dictionary, node_id)
        self.object_dictionary = object_dictionary

        self.id = node_id or self.object_dictionary.node_id
