Layer Setting Services (LSS)
================================

The LSS protocol is used to change the node id and baud rate
of the target CANOpen device. To change these values, configuration mode should be set
first. Then modify the node id and the baud rate.
Once you finished the setting, the values should be saved to non-volatile memory.
Finally, you can switch to normal mode.

To use this protocol, only one LSS slave should be connected in CAN bus.

.. note::
    Only the node id and baud rate are supported in :class:`canopen.LssMaster`

Examples
--------

Switch the target device into CONFIGURATION mode::

    network.lss.send_switch_mode_global(network.lss.CONFIGURATION_MODE)

You can read the current node id of the LSS slave::

    node_id = network.lss.inquire_node_id()

Change the node id and baud rate::

    network.lss.configure_node_id(node_id+1)
    network.lss.configure_bit_timing(2)

This is the table for converting the argument index of bit timing into baud rate.

    ==== ===============
    idx  Baud rate
    ==== ===============
    0    1 MBit/sec
    1    800 kBit/sec
    2    500 kBit/sec
    3    250 kBit/sec
    4    125 kBit/sec
    5    100 kBit/sec
    6    50 kBit/sec
    7    20 kBit/sec
    8    10 kBit/sec
    ==== ===============

Save the configuration::

    network.lss.store_configuration()

Finally, you can switch the state of target device from CONFIGURATION mode to NORMAL mode::

    network.lss.send_switch_mode_global(network.lss.NORMAL_MODE)


API
---

.. autoclass:: canopen.lss.LssMaster
   :members:


.. autoclass:: canopen.lss.LssError
   :show-inheritance:
   :members:

.. _python-can: https://python-can.readthedocs.org/en/stable/
