import os.path
import unittest
import time
from functools import partial
import canopen
from canopen import nmt, LocalNode, RemoteNode
from canopen.objectdictionary import Variable, Record
import canopen.objectdictionary.datatypes as dtypes
from canopen.pdo import RemoteRPDO
import logging
from random import seed, randint
import threading
import struct


seed(333)


SENSOR_EDS_PATH = os.path.join(os.path.dirname(__file__), 'sensor.eds')
SENSOR_MASTER_EDS_PATH = os.path.join(os.path.dirname(__file__),
                                      'sensor_master.eds')


logging.basicConfig(level=logging.WARNING)
logger = logging.getLogger(__name__)


class Sensor(canopen.LocalNode):
    """A sensor device"""
    def __init__(self, node_id):
        canopen.LocalNode.__init__(self, node_id, SENSOR_EDS_PATH)

        correction_factor_var = self.get_object('Correction_Factor')
        self.correction_factor = correction_factor_var.raw
        correction_factor_var.add_callback(self.onNewFactor)

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

    def associate_network(self, network):
        canopen.LocalNode.associate_network(self, network)
        # Start 'measuring'
        self.do_measure = threading.Event()
        self.do_measure.set()
        self._measure = threading.Thread(target=self.measure)
        self._measure.daemon = True
        self._measure.start()

    def remove_network(self):
        """Specialized child function to stop the daemonized measurement
        thread"""
        self.do_measure.clear()
        canopen.LocalNode.remove_network(self)


class NetworkMaster(canopen.LocalNode):
    """The data collection instance of the network"""
    def __init__(self, node_id):
        """Specialization of the LocalNode method"""
        canopen.LocalNode.__init__(self, node_id, SENSOR_MASTER_EDS_PATH)
        self.internal_var_base = 0x6060
        self.active_sensors = {}

    def associate_network(self, network):
        """Specialization of the LocalNode method"""
        canopen.LocalNode.associate_network(self, network)
        # Start listening for hearbeat signals of the first 50 nodes
        for node_id in range(1, 50):
            can_id = node_id + 0x700
            self.network.subscribe(can_id, self.on_sensor_heartbeat)

    def remove_network(self):
        """Specialization of the LocalNode method"""
        for node_id in range(1, 50):
            self.network.unsubscribe(node_id + 0x700)
        for sensor_node in self.active_sensors.values():
            sensor_node.nmt.state = "STOPPED"
            sensor_node.remove_network()
        self.active_sensors = {}
        canopen.LocalNode.remove_network(self)

    def on_sensor_heartbeat(self, can_id, data, timestamp):
        """Callback for hearbeat reception. This is used as a node detection
        mechanism: When a node connects to the network it sends heartbeat
        messages, which serve the network master to keep track of the active
        nodes on the network. Every node that is not yet known to the master is
        registered in an internal lookup table."""
        state = struct.unpack_from("<B", data)[0]
        state = nmt.NMT_STATES[state]
        node_id = can_id - 0x700
        if state in ['PRE-OPERATIONAL', 'OPERATIONAL'] and node_id not in self.active_sensors:
            # New node that we still don't know yet
            sensor_node = RemoteNode(node_id, SENSOR_EDS_PATH)
            sensor_value = sensor_node.get_object("Sensor_Value")
            sensor_value.add_callback(partial(self.on_sensor_update,
                                              sensor_node))
            sensor_node.associate_network(self.network)
            sensor_node.nmt.state = "OPERATIONAL"
            self.active_sensors[node_id] = sensor_node

        elif state != 'OPERATIONAL' and node_id in self.active_sensors:
            # Sensor not longer operational -> remove from active sensors
            sensor_node = self.active_sensors.pop(node_id)
            sensor_node.remove_network()

    def on_sensor_update(self, sensor, index, subindex, value):
        """Callback if the sensor data of a sensor changes. Write the new data
        in our active sensors dictionary.

        This could be used for all sorts of things. We know the sensor node
        that was updated and the index, subindex and value of its
        object dictionary entry"""
        pass

    def set_correction_factor(self, factor):
        """Simple helper function"""
        self.set_value('Correction_Factor', 0, factor)


class TestDemo(unittest.TestCase):
    """
    A demo implementation of the canopen features. This test demo is not working
    with asserts, instead it uses all kinds of features of this library and
    expects that they don't fail (e.g. with exception).

    This can serve as a very good show case of the possible interactions of this
    library when run with a debug level of *DEBUG* or *INFO*.

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
          connected to the network, so it 'allocates' them dynamically.
    """

    def setUp(self):
        self.master_network = canopen.Network()
        self.sensor_network = canopen.Network()
        # Connect to a virtual network to allow for OS independent tests
        self.master_network.connect(channel="demo", bustype="virtual",
                                    receive_own_messages=True)
        self.sensor_network.connect(channel="demo", bustype="virtual",
                                    receive_own_messages=True)
        self.master_node = NetworkMaster(1)
        self.master_node.associate_network(self.master_network)
        time.sleep(0.5)
        self.sensors = [
            Sensor(5),
            Sensor(8),
            Sensor(12),
        ]
        for sensor in self.sensors:
            sensor.associate_network(self.sensor_network)
            sensor.nmt.state = "PRE-OPERATIONAL"

    def tearDown(self):
        self.master_node.remove_network()
        for sensor in self.sensors:
            sensor.remove_network()
        self.sensor_network.disconnect()
        self.master_network.disconnect()

    def test_demo(self):
        n = 0
        total_iterations = 4
        half_iterations = total_iterations // 2
        while n < total_iterations:
            time.sleep(1)
            n += 1
            if n == half_iterations:
                logger.info("\nValues at iteration after half the iterations:")
                for sensor in self.master_node.active_sensors.values():
                    curr_value = sensor.get_value("Sensor_Value")
                    curr_factor = sensor.get_value("Correction_Factor")
                    logger.info("  Sensor #{}: {} with factor {}".format(sensor.id,
                                                                   curr_value,
                                                                   curr_factor))
                curr_factor = self.master_node.get_value("Correction_Factor")
                # Set the new factor. This will broadcast to all nodes on the
                # network, which should cause their values to change
                self.master_node.set_correction_factor(0.5)
        logger.info("Values at the end:")
        for sensor in self.master_node.active_sensors.values():
            curr_value = sensor.get_value("Sensor_Value")
            curr_factor = sensor.get_value("Correction_Factor")
            logger.info("  Sensor #{}: {} with factor {}".format(sensor.id,
                                                           curr_value,
                                                           curr_factor))

