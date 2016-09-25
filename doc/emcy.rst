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




API
---

.. autoclass:: canopen.emcy.EmcyConsumer
    :members:

.. autoexception:: canopen.emcy.EmcyError
    :members:
