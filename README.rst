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

If you want to be able to change the code while using it, clone it then install
it in `develop mode`_::

    $ git clone git@github.com:christiansandberg/canopen.git
    $ cd canopen
    $ pip install -e .


Documentation
-------------

Documentation can be found on Read the Docs:

http://canopen.readthedocs.io/

It can also be generated from a local clone using Sphinx_::

    $ python setup.py build_sphinx


Hardware support
----------------

This library supports multiple hardware and drivers through the python-can_ package.
At the time of writing this includes:

* SocketCAN on Linux
* Kvaser
* Peak CAN
* IXXAT
* USB2CAN

It is also possible to integrate this library with a custom backend.


Quick Start
-----------

Here are some quick examples of what you can do:


.. code-block:: python

    import canopen

    # Start with creating a network representing one CAN bus
    network = canopen.Network()

    # Add some nodes with corresponding Object Dictionaries
    node = network.add_node(6, '/path/to/object_dictionary.eds')
    network.add_node(7, '/path/to/object_dictionary.eds')

    # Connect to the CAN bus
    # Arguments are passed to a python-can bus
    # (see https://python-can.readthedocs.io/en/latest/bus.html).
    network.connect(channel=0, bustype='kvaser', bitrate=250000)

    # Read a variable using SDO
    device_name = node.sdo['ManufacturerDeviceName'].raw
    vendor_id = node.sdo[0x1018][1].raw

    # Read PDO configuration from node
    node.pdo.read()
    # Transmit SYNC every 100 ms
    network.sync.start(0.1)

    # Change state to operational (NMT start)
    network[6].nmt.state = 'OPERATIONAL'
    network[7].nmt.state = 'OPERATIONAL'

    # Read a value from Tx PDO 1
    node.pdo.tx[1].wait_for_reception()
    speed = node.pdo.tx[1]['ApplicationStatus.ActualSpeed'].phys

    # Disconnect from CAN bus
    network.sync.stop()
    network.disconnect()


TODO
----

There are a lot of things that still needs implementing and fixing.
Pull requests are most welcome!

* Documentation (docs + API)
* Unit tests
* Period transmit using BCM
* SDO block transfer
* TIME
* XDD support


.. _PyPI: https://pypi.python.org/pypi/canopen
.. _CANopen: https://en.wikipedia.org/wiki/CANopen
.. _python-can: https://python-can.readthedocs.org/en/stable/
.. _Sphinx: http://www.sphinx-doc.org/
.. _develop mode: https://packaging.python.org/distributing/#working-in-development-mode
