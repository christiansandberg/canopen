A Python implementation of the CANopen standard. The application will act as a master.


Examples
--------

Here are some quick examples:


.. code-block:: python

    import canopen

    # Start with creating a network representing one CAN bus
    network = canopen.Network()

    # Add some nodes with corresponding Object Dictionaries
    network.add_node(6, '/path/to/object_dictionary.eds')
    network.add_node(7, '/path/to/object_dictionary.eds')

    # Connect to the CAN bus
    # Arguments are passed to a `python-can bus <https://python-can.readthedocs.io/en/latest/bus.html>`_.
    network.connect(channel=0, bustype='kvaser', bitrate=250000)

    # Read a parameter using SDO
    vendor_id = network[6].sdo[0x1018][1].raw
    device_name = network[6].sdo['ManufacturerDeviceName']['ManufacturerDeviceName'].raw

    # Change state to operational (NMT start)
    network[6].nmt.state = 'OPERATIONAL'
    network[7].nmt.state = 'OPERATIONAL'

    # Disconnect from CAN bus
    network.disconnect()
