Network (CAN bus)
=================

The :class:`canopen.Network` represents a collection of nodes connected to the
same CAN bus. This handles the sending and receiving of messages and dispatches
messages to the nodes it knows about.


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

.. _python-can: https://python-can.readthedocs.org/en/stable/
