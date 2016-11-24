Emergency Object (EMCY)
=======================

Emergency messages are triggered by the occurrence of a device internal fatal
error situation and are transmitted from the concerned application device to the
other devices with high priority. This makes them suitable for interrupt type
error alerts. An Emergency Telegram may be sent only once per 'error event',
i.e. the emergency messages must not be repeated. As long as no new errors occur
on a device no further emergency message must be sent.
By means of CANopen Communication Profile defined emergency error codes,
the error register and device specific additional information are specified in
the device profiles.


Examples
--------

To list the currently active emergencies for a particular node, one can use the
``.active`` attribute which is a list of :class:`canopen.emcy.EmcyError`
objects::

    active_codes = [emcy.code for emcy in node.emcy.active]
    all_codes = [emcy.code for emcy in node.emcy.log]

The :class:`canopen.emcy.EmcyError` objects are actually exceptions so that they
can be easily raised if that's what you want::

    if node.emcy.active:
        raise node.emcy.active[-1]


API
---

.. autoclass:: canopen.emcy.EmcyConsumer
    :members:

.. autoexception:: canopen.emcy.EmcyError
    :members:
