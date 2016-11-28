Network and nodes
=================

The :class:`canopen.Network` represents a collection of nodes connected to the
same CAN bus. This handles the sending and receiving of messages and dispatches
messages to the nodes it knows about.

Each node is represented using the :class:`canopen.Node` class. It is usually
associated with an object dictionary and each service has its own attribute
owned by this node.


Examples
--------

Create one network per CAN bus::

    import canopen

    network = canopen.Network()

By default this library uses python-can_ for the actual communication.
See its documentation for specifics on how to configure your specific interface.

Call the ``connect()`` method to start the communication, optionally providing
arguments passed to a the :class:`can.BusABC` constructor::

    network.connect(channel='can0', bustype='socketcan')

Add nodes to the network using the ``add_node()`` method::

    node = network.add_node(6, '/path/to/object_dictionary.eds')

Nodes can also be accessed using the ``Network`` object as a Python dictionary::

    for node_id in network:
        print(network[node_id])

Finally, make sure to disconnect after you are done::

    network.disconnect()


API
---

.. autoclass:: canopen.Network
   :members:

   .. py:attribute:: nmt

      The broadcast :class:`canopen.nmt.NmtMaster` which will affect all nodes.

   .. py:attribute:: sync

      The :class:`canopen.sync.SyncProducer` for this network.

   .. describe:: network[node_id]

      Return the :class:`canopen.Node` for the specified node ID.

   .. describe:: iter(network)

      Return an iterator over the handled node IDs.

   .. describe:: node_id in network

      Return ``True`` if the node ID exists is handled by this network.

   .. describe:: del network[node_id]

      Delete the node ID from the network.

   .. method:: values()

      Return a list of :class:`canopen.Node` handled by this network.


.. autoclass:: canopen.Node
    :members:

    .. py:attribute:: id

       The node id (1 - 127). Changing this after initializing the object
       will not have any effect.

    .. py:attribute:: sdo

       The :class:`canopen.sdo.SdoClient` associated with the node.

    .. py:attribute:: pdo

       The :class:`canopen.pdo.PdoNode` associated with the node.

    .. py:attribute:: nmt

       The :class:`canopen.nmt.NmtMaster` associated with the node.

    .. py:attribute:: emcy

       The :class:`canopen.emcy.EmcyConsumer` associated with the node.

    .. py:attribute:: object_dictionary

       The :class:`canopen.ObjectDictionary` associated with the node

    .. py:attribute:: network

       The :class:`canopen.Network` owning the node


.. _python-can: https://python-can.readthedocs.org/en/stable/
