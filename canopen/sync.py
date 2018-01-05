

class SyncProducer(object):
    """Transmits a SYNC message periodically."""

    #: COB-ID of the SYNC message
    cob_id = 0x80

    def __init__(self, network):
        self.network = network
        self.period = None
        self._task = None

    def transmit(self):
        """Send out a SYNC message once."""
        self.network.send_message(self.cob_id, [])

    def start(self, period=None):
        """Start periodic transmission of SYNC message in a background thread.

        :param float period:
            Period of SYNC message in seconds.
        """
        if period is not None:
            self.period = period

        if not self.period:
            raise ValueError("A valid transmission period has not been given")

        self._task = self.network.send_periodic(self.cob_id, [], self.period)

    def stop(self):
        """Stop periodic transmission of SYNC message."""
        self._task.stop()
