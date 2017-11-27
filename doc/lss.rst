Layer Setting Services (LSS)
================================

The LSS protocol is used to change the node id and baud rate
of the target CANOpen device (slave). To change these values, configuration state should be set
first by master. Then modify the node id and the baud rate.
There are two options to switch from waiting state to configuration state.
One is to switch all the slave at once, the other way is to switch only one slave.
The former can be used to set baud rate for all the slaves.
The latter can be used to change node id one by one.

Once you finished the setting, the values should be saved to non-volatile memory.
Finally, you can switch to LSS waiting state.

.. note::
    Some method and constance names are changed::

        send_switch_mode_global() ==> send_switch_state_global()
        network.lss.CONFIGURATION_MODE ==> network.lss.CONFIGURATION_STATE



.. note::
    Fastscan is not supported.

Examples
--------

If you want to switch all the slaves at once, run the following command::

    network.lss.send_switch_state_global(network.lss.WAITING_STATE)

There is no response for the command
Or, you can run this command if you want to switch only one slave::

    ret_bool = network.lss.send_switch_state_selective(vendorId, productCode,
                                        revisionNumber, serialNumber)


Switch all the slave into CONFIGURATION mode::


If you want to switch all the slaves at once, run the following command::

    network.lss.send_switch_state_global(network.lss.WAITING_STATE)

There is no response for the command
Or, you can run this command if you want to switch only one slave::

    ret_bool = network.lss.send_switch_state_selective(vendorId, productCode,
                                        revisionNumber, serialNumber)



    network.lss.send_state_mode_global(network.lss.CONFIGURATION_STATE)

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

    network.lss.send_switch_state_global(network.lss.WAITING_STATE)


API
---

.. autoclass:: canopen.lss.LssMaster
   :members:


.. autoclass:: canopen.lss.LssError
   :show-inheritance:
   :members:

.. _python-can: https://python-can.readthedocs.org/en/stable/
