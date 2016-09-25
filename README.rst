CANopen for Python
==================

A Python implementation of the CANopen_ standard.


Features
--------

* NMT master
* SDO client
* PDO producer/consumer
* SYNC producer
* EMCY consumer


Installation
------------

Install from PyPI_ using pip::

    $ pip install canopen


Documentation
-------------

Documentation can be found on Read the Docs:

http://canopen.readthedocs.io/

It can also be generated locally using Sphinx_::

    $ python setup.py build_sphinx


Hardware support
----------------

This library support multiple hardware and drivers through the python-can_ package.
At the time of writing this includes:

* Kvaser
* Peak CAN
* IXXAT
* USB2CAN
* Anything supported by socketcan on Linux

It is also possible to integrate this library with a custom backend.


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
    # Arguments are passed to a python-can bus
    # (see https://python-can.readthedocs.io/en/latest/bus.html).
    network.connect(channel=0, bustype='kvaser', bitrate=250000)

    # Read a variable using SDO
    device_name = network[6].sdo['ManufacturerDeviceName'].raw
    vendor_id = network[6].sdo[0x1018][1].raw

    # .phys takes factor into consideration (if supported)
    network[6].sdo['ApplicationCommands']['CommandSpeed'].phys = 1502.3

    # Accessing value descriptions as strings (if supported)
    network[6].sdo['ApplicationCommands']['RequestedControlMode'].desc = 'Speed Mode'

    # Accessing individual bits
    network[6].sdo['ApplicationCommands']['CommandAll'].bits[2:3] = 2

    # Change state to operational (NMT start)
    network[6].nmt.state = 'OPERATIONAL'
    network[7].nmt.state = 'OPERATIONAL'

    # Disconnect from CAN bus
    network.disconnect()


TODO
----

There are a lot of things that still needs implementing and fixing.
Pull requests are most welcome!

* Documentation (docs + API)
* Unit tests
* SDO block transfer
* TIME
* XDD support


.. _PyPI: https://pypi.python.org/pypi/canopen
.. _CANopen: https://en.wikipedia.org/wiki/CANopen
.. _python-can: https://python-can.readthedocs.org/en/stable/
.. _Sphinx: http://www.sphinx-doc.org/
