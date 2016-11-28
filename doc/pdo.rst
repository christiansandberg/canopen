Process Data Object (PDO)
=========================

The Process Data Object protocol is used to process real time data among various
nodes. You can transfer up to 8 bytes (64 bits) of data per one PDO either from
or to the device. One PDO can contain multiple object dictionary entries and the
objects within one PDO are configurable using the mapping and parameter object
dictionary entries.

There are two kinds of PDOs: transmit and receive PDOs (TPDO and RPDO).
The former is for data coming from the device and the latter is for data going
to the device; that is, with RPDO you can send data to the device and with TPDO
you can read data from the device. In the pre-defined connection set there are
identifiers for four (4) TPDOs and four (4) RPDOs available.
With configuration 512 PDOs are possible.

PDOs can be sent synchronously or asynchronously. Synchronous PDOs are sent
after the SYNC message whereas asynchronous messages are sent after internal
or external trigger. For example, you can make a request to a device to transmit
TPDO that contains data you need by sending an empty TPDO with the RTR flag
(if the device is configured to accept TPDO requests).

With RPDOs you can, for example, start two devices simultaneously.
You only need to map the same RPDO into two or more different devices and make
sure those RPDOs are mapped with the same COB-ID.


Examples
--------

A :class:`canopen.Node` has a ``.pdo`` attribute that can be used to interact
with the node using PDOs. This is in turn divided in a ``.tx`` and a ``.rx``
attribute which can be subindexed to specify which message to use (first map
starts at 1, not 0)::

    # Read current PDO configuration
    node.pdo.read()

    # Do some changes to TxPDO4 and RxPDO4
    node.pdo.tx[4].clear()
    node.pdo.tx[4].add_variable('ApplicationStatus', 'StatusAll')
    node.pdo.tx[4].add_variable('ApplicationStatus', 'ActualSpeed')
    node.pdo.tx[4].trans_type = 1
    node.pdo.tx[4].enabled = True

    node.pdo.rx[4].clear()
    node.pdo.rx[4].add_variable('ApplicationCommands', 'CommandAll')
    node.pdo.rx[4].add_variable('ApplicationCommands', 'CommandSpeed')
    node.pdo.rx[4].enabled = True

    # Save new configuration (node must be in pre-operational)
    node.nmt.state = 'PRE-OPERATIONAL'
    node.pdo.save()

    # Start SYNC message with a period of 10 ms
    network.sync.start(0.01)

    # Start RxPDO4 with an interval of 100 ms
    node.pdo.rx[4]['ApplicationCommands.CommandSpeed'].phys = 1000
    node.pdo.rx[4].start(0.1)
    node.nmt.state = 'OPERATIONAL'

    # Read 50 values of speed and save to a file
    with open('output.txt', 'w') as f:
        for i in range(50):
            node.pdo.tx[4].wait_for_reception()
            speed = node.pdo.tx[4]['ApplicationStatus.ActualSpeed'].phys
            f.write('%s\n' % speed)

    # Stop transmission of RxPDO and SYNC
    node.pdo.rx[4].stop()
    network.sync.stop()


API
---

.. autoclass:: canopen.pdo.PdoNode
   :members:

   .. py:attribute:: rx

      The :class:`canopen.pdo.Maps` object representing the receive PDO maps.

   .. py:attribute:: tx

      The :class:`canopen.pdo.Maps` object representing the transmit PDO maps.


.. autoclass:: canopen.pdo.Maps
   :members:

   .. describe:: maps[no]

      Return the :class:`canopen.pdo.Map` for the specified map number.
      First map starts at 1.

   .. describe:: iter(maps)

      Return an iterator of the available map numbers.

   .. describe:: len(maps)

      Return the number of supported maps.


.. autoclass:: canopen.pdo.Map
   :members:

   .. describe:: map[name]

      Return the :class:`canopen.pdo.Variable` for the variable specified as
      ``"Group.Variable"`` or ``"Variable"`` or as a position starting at 0.

   .. describe:: iter(map)

      Return an iterator of the :class:`canopen.pdo.Variable` entries in the map.

   .. describe:: len(map)

      Return the number of variables in the map.


.. autoclass:: canopen.pdo.Variable
   :members:
   :inherited-members:

   .. py:attribute:: od

      The :class:`canopen.objectdictionary.Variable` associated with this object.
