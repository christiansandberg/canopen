import os.path
import unittest
import time
import canopen
import logging
from random import seed, randint
import threading


seed(333)


SENSOR_EDS_PATH = os.path.join(os.path.dirname(__file__), 'sensor.eds')
SENSOR_MASTER_EDS_PATH = os.path.join(os.path.dirname(__file__),
                                      'sensor_master.eds')


logging.basicConfig(level=logging.WARNING)


class Sensor(canopen.LocalNode):
    """A sensor device"""
    def __init__(self, node_id):
        canopen.LocalNode.__init__(self, node_id, SENSOR_EDS_PATH)

        correction_factor_var = self.get_object('Correction_Factor')
        self.correction_factor = correction_factor_var.raw
        correction_factor_var.add_callback(self.onNewFactor)

        self.do_measure = threading.Event()
        self.do_measure.set()
        self._measure = threading.Thread(target=self.measure)
        self._measure.daemon = True
        self._measure.start()

    def onNewFactor(self, index, subindex, data):
        """Variable change callback function
        When the object dictionary variable for the correction value changes,
        then this function is called and writes the new value into the class
        variable."""

        self.correction_factor = self.get_value('Correction_Factor')

    def measure(self):
        """This function simulates a sensor measurement.
        We fluctuate around some base value (measurement jitter). In addition
        we include the correction factor into the calculation."""
        base_value = 10000
        try:
            while self.do_measure.is_set():
                val = int(self.correction_factor *
                          (base_value + randint(-500, 500)))
                self.set_value('Sensor_Value', 0, val)
                time.sleep(0.25)
        except Exception as exc:
            self.exception = exc
            raise

    def remove_network(self):
        """Specialized child function to stop the daemonized measurement
        thread"""
        self.do_measure.clear()
        canopen.LocalNode.remove_network(self)


class NetworkMaster(canopen.RemoteNode):
    """The data collection instance of the network"""
    def __init__(self, node_id):
        canopen.Remote.__init__(self, node_id, SENSOR_MASTER_EDS_PATH)


class TestDemo(unittest.TestCase):
    """
    A demo implementation of the canopen features.

    The scenario:
        We are the network master, a data collection device. The data we are
        collecting comes from a number of sensors. Each sensor can only measure
        one thing and sends its data as process data (PDO). In addition every
        sensor has a correction factor which it uses to compensate for errors
        due to ambient constraints. The sensors are not able to determine that
        correction factor themselves, instead the network master sends them the
        value of this factor via PDO.
    Network Settings:
        * The sensors send their data via COB-ID 0x400 + node ID
        * The sensors receive the correction factor on COB-ID 0x222
        * The network master does not know in advance which sensors are
          connected to the network
    """

    def setUp(self):
        self.network = canopen.Network()
        # Connect to a virtual network to allow for OS independent tests
        self.network.connect(channel="demo", bustype="virtual",
                             receive_own_messages=True)
        self.master_node = NetworkMaster(1)
        self.master_node.associate_network(self.network)
        time.sleep(0.5)
        self.sensors = [
            Sensor(5),
            Sensor(8),
            Sensor(12),
        ]
        for sensor in self.sensors:
            sensor.associate_network(self.network)
            sensor.nmt.state = "PRE-OPERATIONAL"

    def tearDown(self):
        self.master_node.remove_network()
        for sensor in self.sensors:
            sensor.remove_network()
        self.network.disconnect()

    def test_demo(self):
        pass
