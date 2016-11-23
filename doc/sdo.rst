Service Data Object (SDO)
=========================

The SDO protocol is used for setting and for reading values from the
object dictionary of a remote device. The device whose object dictionary is
accessed is the SDO server and the device accessing the remote device is the SDO
client. The communication is always initiated by the SDO client. In CANopen
terminology, communication is viewed from the SDO server, so that a read from an
object dictionary results in an SDO upload and a write to a dictionary entry is
an SDO download.

Because the object dictionary values can be larger than the eight bytes limit of
a CAN frame, the SDO protocol implements segmentation and desegmentation of
longer messages. Actually, there are two of these protocols: SDO download/upload
and SDO Block download/upload. The SDO block transfer is a newer addition to
standard, which allows large amounts of data to be transferred with slightly
less protocol overhead.

.. note::
    SDO block transfers are not yet supported.

The COB-IDs of the respective SDO transfer messages from client to server and
server to client can be set in the object dictionary. Up to 128 SDO servers can
be set up in the object dictionary at addresses 0x1200 - 0x127F. Similarly, the
SDO client connections of the device can be configured with variables at
0x1280 - 0x12FF. However the pre-defined connection set defines an SDO channel
which can be used even just after bootup (in the Pre-operational state) to
configure the device. The COB-IDs of this channel are 0x600 + node ID for
receiving and 0x580 + node ID for transmitting.


Examples
--------

SDO objects can be accessed using the ``.sdo`` member which works like a Python
dictionary. Indexes and subindexes can be identified by either name or number.
The code below only creates objects, no messages are sent or received yet::

    # Complex records
    command_all = node.sdo['ApplicationCommands']['CommandAll']
    actual_speed = node.sdo['ApplicationStatus']['ActualSpeed']
    control_mode = node.sdo['ApplicationSetupParameters']['RequestedControlMode']

    # Simple variables
    device_type = node.sdo[0x1000]

    # Arrays
    error_log = node.sdo[0x1003]

To actually read or write the variables, use the ``.raw``, ``.phys``, ``.desc``,
or ``.bits`` attributes::

    print("The device type is 0x%X" % device_type.raw)

    # Using value descriptions instead of integers (if supported by OD)
    control_mode.desc = 'Speed Mode'

    # Set individual bit
    command_all.bits[3] = 1

    # Read and write physical values scaled by a factor (if supported by OD)
    print("The actual speed is %f rpm" % actual_speed.phys)

    # Iterate over arrays or records
    for error in error_log.values():
        print("Error 0x%X was found in the log" % error.raw)


API
---

.. autoclass:: canopen.sdo.SdoClient
    :members:

    .. describe:: c[index]

       Return the SDO object for the specified index (as int) or name
       (as string).

    .. describe:: iter(c)

       Return an iterator over the indexes from the object dictionary.

    .. describe:: index in c

       Return ``True`` if the index (as int) or name (as string) exists in
       the object dictionary.

    .. describe:: len(c)

       Return the number of indexes in the object dictionary.

    .. method:: values()

       Return a list of objects (records, arrays and variables).


.. autoclass:: canopen.sdo.Variable
    :members:
    :inherited-members:


.. autoclass:: canopen.sdo.Record
    :members:

    .. describe:: record[subindex]

       Return the :class:`canopen.sdo.Variable` for the specified subindex
       (as int) or name (as string).

    .. describe:: iter(record)

       Return an iterator over the subindexes from the record.

    .. describe:: subindex in record

       Return ``True`` if the subindex (as int) or name (as string) exists in
       the record.

    .. describe:: len(record)

       Return the number of subindexes in the record.

    .. method:: values()

       Return a list of :class:`canopen.sdo.Variable` in the record.


.. autoclass:: canopen.sdo.Array
    :members:

    .. describe:: array[subindex]

       Return the :class:`canopen.sdo.Variable` for the specified subindex
       (as int) or name (as string).

    .. describe:: iter(array)

       Return an iterator over the subindexes from the array.
       This will make a SDO read operation on subindex 0 in order to get the
       actual length of the array.

    .. describe:: subindex in array

       Return ``True`` if the subindex (as int) or name (as string) exists in
       the array.
       This will make a SDO read operation on subindex 0 in order to get the
       actual length of the array.

    .. describe:: len(array)

       Return the length of the array.
       This will make a SDO read operation on subindex 0.

    .. method:: values()

       Return a list of :class:`canopen.sdo.Variable` in the array.
       This will make a SDO read operation on subindex 0 in order to get the
       actual length of the array.


Exceptions
~~~~~~~~~~

.. autoexception:: canopen.SdoAbortedError
    :members:

.. autoexception:: canopen.SdoCommunicationError
    :members:
