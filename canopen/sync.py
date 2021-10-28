

from typing import Optional


class SyncProducer(object):
    """Transmits a SYNC message periodically."""

    #: COB-ID of the SYNC message
    cob_id = 0x80

    def __init__(self, network):
        self.network = network
        self.period: Optional[float] = None
        self._task = None

    def transmit(self, count: Optional[int] = None, alternative_cob_id: int = cob_id):
        """Send out a SYNC message once.

        :param count:
            Counter to add in message.
        :param alternative_cob_id:
            Alternative sync COB-ID. Used when different nodes have different sync COB-IDs.
        """
        data = [count] if count is not None else []
        self.network.send_message(alternative_cob_id, data)

    def start(self, period: Optional[float] = None, alternative_cob_id: int = cob_id):
        """Start periodic transmission of SYNC message in a background thread.

        :param period:
            Period of SYNC message in seconds.
        :param alternative_cob_id:
            Alternative sync COB-ID. Used when different nodes have different sync COB-IDs.
        """
        if period is not None:
            self.period = period

        if not self.period:
            raise ValueError("A valid transmission period has not been given")

        self._task = self.network.send_periodic(alternative_cob_id, [], self.period)

    def stop(self):
        """Stop periodic transmission of SYNC message."""
        if self._task is not None:
            self._task.stop()
