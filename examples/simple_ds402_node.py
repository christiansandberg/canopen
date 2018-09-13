import canopen
import sys
import os
import traceback

import time

try:

    # Start with creating a network representing one CAN bus
    network = canopen.Network()

    # Connect to the CAN bus

    kargs = {'bustype': 'kvaser', 'channel':0, 'bitrate': 1000000}
    network.connect(**kargs)

    #network.connect(bustype='kvaser', channel=0, bitrate=1000000)
    network.check()

    # Add some nodes with corresponding Object Dictionaries
    node = canopen.BaseNode402(35, '/home/andre/Code/test/jupiter.eds')
    network.add_node(node)
    # network.add_node(34, '/home/andre/Code/test/jupiter.eds')
    # node = network[34]

    # Reset network
    node.nmt.state = 'RESET COMMUNICATION'

    node.nmt.wait_for_bootup(15)

    print('node state before bootup = {0}'.format(node.nmt.state))

    # Transmit SYNC every 100 ms
    network.sync.start(0.1)
    node.setup_402_state_machine()

    node.state = 'READY TO SWITCH ON'
    node.state = 'SWITCHED ON'

    node.load_configuration()

    print('node state 3) = {0}'.format(node.state))

    node.op_mode = 'PROFILED POSITION'

    device_name = node.sdo[0x1008].raw
    vendor_id = node.sdo[0x1018][1].raw

    print('Device Name: {0}'.format(device_name))
    print('Vendor ID: {0}'.format(vendor_id))

    node.rpdo.export('database.dbc')

    # -----------------------------------------------------------------------------------------

    try:
        node.state = 'OPERATION ENABLED'

    except RuntimeError as e:
        print e

    print('Node status after operation enabled {0}'.format(node.state))

    # -----------------------------------------------------------------------------------------
    node.nmt.start_node_guarding(0.01)

    time_test = time.time()
    reseted = False

    node.homing()

    while True:
        try:
            network.check()
        except Exception:
            break

        # Read a value from TxPDO1
        node.tpdo[1].wait_for_reception()
        speed = node.tpdo[1]['Velocity actual value'].phys

        print('VEL: {0}'.format(speed))
        print('Statusword: {0}'.format(node.pdo['0x6041'].raw))

        time.sleep(0.001)

        if time.time() > time_test + 120 and not reseted:
            node.reset_from_fault()
            reseted = True

except KeyboardInterrupt:
    pass
except Exception as e:
    exc_type, exc_obj, exc_tb = sys.exc_info()
    fname = os.path.split(exc_tb.tb_frame.f_code.co_filename)[1]
    print(exc_type, fname, exc_tb.tb_lineno)
    traceback.print_exc()
finally:
    # Disconnect from CAN bus
    if network is not None:
        for node_id in network:
            node = network[node_id]
            node.nmt.state = 'PRE-OPERATIONAL'
            node.nmt.stop_node_guarding()
        network.disconnect()

