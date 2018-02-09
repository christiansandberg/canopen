import canopen
import struct
import time
import logging
from pathlib import Path
from pprint import pprint


logging.basicConfig(level=logging.INFO)
eds_root = Path(__file__).parent/"../test"

network = canopen.Network()
network.connect(bustype='socketcan', channel='can0')

eds_path = eds_root/"sample.eds"
node_1 = canopen.LocalNode(1, eds_path.as_posix())
# Set the parameters of the node before we add it to the network
node_1.set_data(0x4321, 1, struct.pack("<h", 42))
node_1.set_data(0x4321, 2, struct.pack("<B", 1))
node_1.set_data(0x4321, 3, struct.pack("<b", -10))
node_1.set_data(0x4321, 4, struct.pack("<i", 10))

network.add_node(node_1)
# Finished with initialization so set to pre-opertaional state
node_1.nmt.state = 'PRE-OPERATIONAL'
node_1.nmt.state = 'OPERATIONAL'


try:
    while True:
        time.sleep(0.01)

except KeyboardInterrupt:
    print("Stopping node emulation")
    print("Current internal data store:")
    pprint(node_1.data_store)
