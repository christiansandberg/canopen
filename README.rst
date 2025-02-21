CANopen for Python, asyncio port
================================

A Python implementation of the CANopen_ standard.
The aim of the project is to support the most common parts of the CiA 301
standard in a simple Pythonic interface. It is mainly targeted for testing and
automation tasks rather than a standard compliant master implementation.

The library supports Python 3.8 or newer.

This library is the asyncio port of CANopen. See below for code example.


Async status
------------

The remaining work for feature complete async implementation:

* Implement :code:`ABlockUploadStream`, :code:`ABlockDownloadStream` and
  :code:`ATextIOWrapper` for async in :code:`SdoClient`

* Implement :code:`EcmyConsumer.wait()` for async

* Implement async in :code:`LssMaster``

* Async implementation of :code:`BaseNode402`

* Implement async variant of :code:`Network.add_node`. This will probably also
  add need of async variant of :code:`input_from_node` in eds.py

* Update unittests for async

* Update documentation and examples


Features
--------

The library is mainly meant to be used as a master.

* NMT master
* SDO client
* PDO producer/consumer
* SYNC producer
* EMCY consumer
* TIME producer
* LSS master
* Object Dictionary from EDS
* 402 profile support

Incomplete support for creating slave nodes also exists.

* SDO server
* PDO producer/consumer
* NMT slave
* EMCY producer
* Object Dictionary from EDS


Installation
------------

Install from PyPI_ using :program:`pip`::

    $ pip install canopen

Install from latest ``master`` on GitHub::

    $ pip install https://github.com/christiansandberg/canopen/archive/master.zip

If you want to be able to change the code while using it, clone it then install
it in `develop mode`_::

    $ git clone https://github.com/christiansandberg/canopen.git
    $ cd canopen
    $ pip install -e .

Unit tests can be run using the pytest_ framework::

    $ pip install -r requirements-dev.txt
    $ pytest -v

You can also use :mod:`unittest` standard library module::

    $ python3 -m unittest discover test -v

Documentation
-------------

Documentation can be found on Read the Docs:

http://canopen.readthedocs.io/en/latest/

It can also be generated from a local clone using Sphinx_::

    $ pip install -r doc/requirements.txt
    $ make -C doc html


Hardware support
----------------

This library supports multiple hardware and drivers through the python-can_ package.
See `the list of supported devices <https://python-can.readthedocs.io/en/stable/configuration.html#interface-names>`_.

It is also possible to integrate this library with a custom backend.


Quick start
-----------

Here are some quick examples of what you can do:

The PDOs can be access by three forms:

**1st:** :code:`node.tpdo[n]` or :code:`node.rpdo[n]`

**2nd:** :code:`node.pdo.tx[n]` or :code:`node.pdo.rx[n]`

**3rd:** :code:`node.pdo[0x1A00]` or :code:`node.pdo[0x1600]`

The :code:`n` is the PDO index (normally 1 to 4). The second form of access is for backward compatibility.

.. code-block:: python

    import canopen

    # Start with creating a network representing one CAN bus
    network = canopen.Network()

    # Add some nodes with corresponding Object Dictionaries
    node = canopen.RemoteNode(6, '/path/to/object_dictionary.eds')
    network.add_node(node)

    # Connect to the CAN bus
    # Arguments are passed to python-can's can.Bus() constructor
    # (see https://python-can.readthedocs.io/en/latest/bus.html).
    network.connect()
    # network.connect(interface='socketcan', channel='can0')
    # network.connect(interface='kvaser', channel=0, bitrate=250000)
    # network.connect(interface='pcan', channel='PCAN_USBBUS1', bitrate=250000)
    # network.connect(interface='ixxat', channel=0, bitrate=250000)
    # network.connect(interface='vector', app_name='CANalyzer', channel=0, bitrate=250000)
    # network.connect(interface='nican', channel='CAN0', bitrate=250000)

    # Read a variable using SDO
    device_name = node.sdo['Manufacturer device name'].raw
    vendor_id = node.sdo[0x1018][1].raw

    # Write a variable using SDO
    node.sdo['Producer heartbeat time'].raw = 1000

    # Read PDO configuration from node
    node.tpdo.read()
    node.rpdo.read()
    # Re-map TPDO[1]
    node.tpdo[1].clear()
    node.tpdo[1].add_variable('Statusword')
    node.tpdo[1].add_variable('Velocity actual value')
    node.tpdo[1].add_variable('Some group', 'Some subindex')
    node.tpdo[1].trans_type = 254
    node.tpdo[1].event_timer = 10
    node.tpdo[1].enabled = True
    # Save new PDO configuration to node
    node.tpdo[1].save()

    # Transmit SYNC every 100 ms
    network.sync.start(0.1)

    # Change state to operational (NMT start)
    node.nmt.state = 'OPERATIONAL'

    # Read a value from TPDO[1]
    node.tpdo[1].wait_for_reception()
    speed = node.tpdo[1]['Velocity actual value'].phys
    val = node.tpdo['Some group.Some subindex'].raw

    # Disconnect from CAN bus
    network.sync.stop()
    network.disconnect()


Asyncio
-------

This library can be used with asyncio.

.. code-block:: python

    import asyncio
    import canopen
    import can

    async def my_node(network, nodeid, od):

        # Create the node object and load the OD
        node = network.add_node(nodeid, od)

        # Read the PDOs from the remote
        await node.tpdo.aread()
        await node.rpdo.aread()

        # Set the module state
        node.nmt.set_state('OPERATIONAL')

        # Set motor speed via SDO
        await node.sdo['MotorSpeed'].aset_raw(2)

        while True:

            # Wait for TPDO 1
            t = await node.tpdo[1].await_for_reception(1)
            if not t:
                continue

            # Get the TPDO 1 value
            rpm = node.tpdo[1]['MotorSpeed Actual'].get_raw()
            print(f'SPEED on motor {nodeid}:', rpm)

            # Sleep a little
            await asyncio.sleep(0.2)

            # Send RPDO 1 with some data
            node.rpdo[1]['Some variable'].set_phys(42)
            node.rpdo[1].transmit()

    async def main():

        # Start with creating a network representing one CAN bus
        network = canopen.Network()

        # Connect to the CAN bus
        # Arguments are passed to python-can's can.Bus() constructor
        # (see https://python-can.readthedocs.io/en/latest/bus.html).
        # Note the loop parameter to enable asyncio operation
        loop = asyncio.get_event_loop()
        network.connect(interface='pcan', bitrate=1000000, loop=loop)

        # Create two independent tasks for two nodes 51 and 52 which will run concurrently
        task1 = asyncio.create_task(my_node(network, 51, '/path/to/object_dictionary.eds'))
        task2 = asyncio.create_task(my_node(network, 52, '/path/to/object_dictionary.eds'))

        # Wait for both to complete (which will never happen)
        await asyncio.gather((task1, task2))

    asyncio.run(main())


Debugging
---------

If you need to see what's going on in better detail, you can increase the
logging_ level:

.. code-block:: python

    import logging
    logging.basicConfig(level=logging.DEBUG)


.. _PyPI: https://pypi.org/project/canopen/
.. _CANopen: https://www.can-cia.org/canopen/
.. _python-can: https://python-can.readthedocs.org/en/stable/
.. _Sphinx: http://www.sphinx-doc.org/
.. _develop mode: https://packaging.python.org/distributing/#working-in-development-mode
.. _logging: https://docs.python.org/3/library/logging.html
.. _pytest: https://docs.pytest.org/
