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

A :class:`canopen.RemoteNode` has :class:`canopen.RemoteNode.rpdo` and
:class:`canopen.RemoteNode.tpdo` attributes that can be used to interact
with the node using PDOs. These can be subindexed to specify which map to use (first map
starts at 1, not 0)::

    # Read current PDO configuration
    node.tpdo.read()
    node.rpdo.read()

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
    # Do not do any blocking operations here!
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

   .. describe:: pdo[no]

      Return the :class:`canopen.pdo.Map` for the specified map number.
      First map starts at 1.

   .. describe:: iter(pdo)

      Return an iterator of the available map numbers.

   .. describe:: len(pdo)

      Return the number of supported maps.


.. autoclass:: canopen.pdo.Map
   :members:

   .. describe:: map[name]

      Return the :class:`canopen.pdo.PdoVariable` for the variable specified as
      ``"Group.Variable"`` or ``"Variable"`` or as a position starting at 0.

   .. describe:: iter(map)

      Return an iterator of the :class:`canopen.pdo.PdoVariable` entries in the map.

   .. describe:: len(map)

      Return the number of variables in the map.


.. autoclass:: canopen.pdo.PdoVariable
   :members:
   :inherited-members:

   .. py:attribute:: od

      The :class:`canopen.objectdictionary.ODVariable` associated with this object.
