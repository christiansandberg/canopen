CANopen for Python
==================

A Python implementation of the CANopen_ standard.
The aim of the project is to support the most common parts of the CiA 301
standard for a master node wrapped in a Pythonic interface.

The library supports Python 2.7 and 3.3+ and runs on Windows, Linux and Mac.


Features
--------

* Object Dictionary from EDS
* NMT master
* SDO client
* PDO producer/consumer
* SYNC producer
* EMCY consumer
* TIME producer


Installation
------------

Install from PyPI_ using pip::

    $ pip install canopen

Install from latest master on GitHub::

    $ pip install https://github.com/christiansandberg/canopen/archive/master.zip

If you want to be able to change the code while using it, clone it then install
it in `develop mode`_::

    $ git clone https://github.com/christiansandberg/canopen.git
    $ cd canopen
    $ pip install -e .


Documentation
-------------

Documentation can be found on Read the Docs:

http://canopen.readthedocs.io/en/latest/

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
* NI-CAN

It is also possible to integrate this library with a custom backend.


Quick start
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
    device_name = node.sdo['Manufacturer device name'].raw
    vendor_id = node.sdo[0x1018][1].raw

    # Write a variable using SDO
    node.sdo['Producer heartbeat time'].raw = 1000

    # Read PDO configuration from node
    node.pdo.read()
    # Transmit SYNC every 100 ms
    network.sync.start(0.1)

    # Change state to operational (NMT start)
    node.nmt.state = 'OPERATIONAL'

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

* More unit test coverage
* Period transmits using python-can cyclic API
* SDO block transfer
* XDD support


.. _PyPI: https://pypi.python.org/pypi/canopen
.. _CANopen: https://en.wikipedia.org/wiki/CANopen
.. _python-can: https://python-can.readthedocs.org/en/stable/
.. _Sphinx: http://www.sphinx-doc.org/
.. _develop mode: https://packaging.python.org/distributing/#working-in-development-mode
