Integration with existing code
==============================

Sometimes you need to use this library together with some existing code base
or you have CAN drivers not supported by python-can. This chapter will cover
some use cases.


Re-using a bus
--------------

If you need to interact with the CAN-bus outside of this library too and you
want to use the same python-can Bus instance, you need to tell the Network
which Bus to use and also add the :class:`canopen.network.MessageListener`
to your existing :class:`can.Notifier`.

Here is a short example::

    import canopen
    import can

    # A Bus instance created outside
    bus = can.interface.Bus()

    network = canopen.Network()
    # Associate the bus with the network
    network.bus = bus

    # Add your list of can.Listener with the network's
    listeners = [can.Printer()] + network.listeners
    # Start the notifier
    notifier = can.Notifier(bus, listeners, 0.5)


Using a custom backend
----------------------

If the python-can package does not have support for your CAN interface then you
need to create a sub-class of :class:`canopen.Network` and provide your own
means of sending messages. You also need to feed incoming messages in a
background thread to :meth:`canopen.Network.notify`.

Here is an example::

    import canopen

    class CustomNetwork(canopen.Network):

        def connect(self, *args, **kwargs):
            # Optionally use this to start communication with CAN
            pass

        def disconnect(self):
            # Optionally use this to stop communincation
            pass

        def send_message(self, can_id, data, remote=False):
            # Send the message with the 11-bit can_id and data which might be
            # a bytearray or list of integers.
            # if remote is True then it should be sent as an RTR.
            pass


    network = CustomNetwork()

    # Should be done in a thread but here we notify the network for
    # demonstration purposes only
    network.notify(0x701, bytearray([0x05]), time.time())
