import time
import threading

from .network import CanError


class SyncProducer(object):
    """Transmits a SYNC message (0x80) periodically."""

    def __init__(self, network):
        self.network = network
        self.period = None
        self.transmit_thread = None
        self.stop_event = threading.Event()

    def transmit(self):
        """Send out a SYNC message once."""
        self.network.send_message(0x80, [])

    def start(self, period=None):
        """Start periodic transmission of SYNC message in a background thread.
        
        :param float period:
            Period of SYNC message in seconds.
        """
        if period is not None:
            self.period = period

        if not self.period:
            raise ValueError("A valid transmission period has not been given")

        if not self.transmit_thread or not self.transmit_thread.is_alive():
            self.stop_event.clear()
            self.transmit_thread = threading.Thread(
                target=self._periodic_transmit)
            self.transmit_thread.daemon = True
            self.transmit_thread.start()

    def stop(self):
        """Stop periodic transmission of SYNC message."""
        self.stop_event.set()
        self.transmit_thread = None

    def _periodic_transmit(self):
        while not self.stop_event.is_set():
            start = time.time()
            try:
                self.transmit()
            except CanError as error:
                print(str(error))
            time_left = self.period - (time.time() - start)
            time.sleep(max(time_left, 0.0))
