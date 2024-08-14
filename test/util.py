import contextlib
import os
import tempfile

from can.interfaces.virtual import VirtualBus
import canopen


DATATYPES_EDS = os.path.join(os.path.dirname(__file__), "datatypes.eds")
SAMPLE_EDS = os.path.join(os.path.dirname(__file__), "sample.eds")

TIMEOUT = 0.1


@contextlib.contextmanager
def tmp_file(*args, **kwds):
    with tempfile.NamedTemporaryFile(*args, **kwds) as tmp:
        tmp.close()
        yield tmp


class VirtualNetwork(canopen.Network):
    def __init__(self):
        super().__init__(VirtualBus())

    def disconnect(self):
        self.notifier.stop(0)
        self.notifier = None
        super().disconnect()
