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
starts at 1, not 0). The :class:`canopen.Node` also allow the user to access 
the PDOs through the attributes ``.rpdo`` and ``.tpdo`` that provide a more
direct way to access the configured PDOs (see example below)::

    # Read current PDO configuration
    node.pdo[4].read()

    # Do some changes to TPDO4 and RPDO4
    node.tpdo[4].clear()
    node.tpdo[4].add_variable('Application Status', 'Status All')
    node.tpdo[4].add_variable('Application Status', 'Actual Speed')
    node.tpdo[4].trans_type = 254
    node.tpdo[4].event_timer = 10
    node.tpdo[4].enabled = True

    node.rpdo[4].clear()
    node.rpdo[4].add_variable('Application Commands', 'Command All')
    node.rpdo[4].add_variable('Application Commands', 'Command Speed')
    node.rpdo[4].enabled = True

    # Save new configuration (node must be in pre-operational)
    node.nmt.state = 'PRE-OPERATIONAL'
    node.tpdo.save()
    node.rpdo.save()
    # Export a database file of PDO configuration
    node.pdo.export('database.dbc')

    # Start RPDO4 with an interval of 100 ms
    node.rpdo[4]['Application Commands.Command Speed'].phys = 1000
    node.rpdo[4].start(0.1)
    node.nmt.state = 'OPERATIONAL'

    # Read 50 values of speed and save to a file
    with open('output.txt', 'w') as f:
        for i in range(50):
            node.tpdo[4].wait_for_reception()
            speed = node.tpdo['Application Status.Actual Speed'].phys
            f.write('%s\n' % speed)

    # Using a callback to asynchronously receive values
    def print_speed(message):
        print('%s received' % message.name)
        for var in message:
            print('%s = %d' % (var.name, var.raw))

    node.tpdo[4].add_callback(print_speed)
    time.sleep(5)

    # Stop transmission of RxPDO
    node.rpdo[4].stop()


API
---

.. autoclass:: canopen.pdo.PdoBase
   :members:

   .. py:attribute:: map

      The :class:`canopen.pdo.Mcps` object representing map associated with the instantiated PDO (transmit or receive).


.. autoclass:: canopen.pdo.PDO
   :members:


.. autoclass:: canopen.pdo.RPDO
   :members:


.. autoclass:: canopen.pdo.TPDO
   :members:

   .. method:: stop()

      Stop transmission of all Tx PDOs.

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
