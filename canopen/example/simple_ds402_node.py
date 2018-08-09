import canopen
import time
from canopen import Node402
import signal

try:
    
    # Start with creating a network representing one CAN bus
    network = canopen.Network()
    
    # Connect to the CAN bus
    network.connect(bustype='kvaser', channel=0, bitrate=1000000)
    
    print 'Bus-state {0}'.format(network.bus.state)
    
    network.check()
    
    # Add some nodes with corresponding Object Dictionaries
    node = Node402(35, '/home/andre/Code/test/jupiter.eds')
    network.add_node(node)
    # network.add_node(34, '/home/andre/Code/test/jupiter.eds')
    # node = network[34]
    
    print '\n\n ##########################################'.format()
    '''
    for obj in node.object_dictionary.values():
        print('0x%X: %s' % (obj.index, obj.name))
        if isinstance(obj, canopen.objectdictionary.Record):
            for subobj in obj.values():
                print('  %d: %s' % (subobj.subindex, subobj.name))

    '''
    print '\n\n ##########################################'.format()

    # Reset network
    node.nmt.state = 'RESET'
    node.nmt.wait_for_bootup(30)
    
    print 'node state 1) = {0}'.format(node.nmt.state)
    
    # Iterate over arrays or records
    error_log = node.sdo[0x1003]
    for error in error_log.values():
        print("Error 0x%X was found in the log" % error.raw)
    
    for node_id in network:
        print(network[node_id])
    
    print 'node state 2) = {0}'.format(node.nmt.state)
    
    # Read a variable using SDO
    
    node.sdo[0x1006].raw = 1
    node.sdo[0x100c].raw = 100
    node.sdo[0x100d].raw = 3
    node.sdo[0x1014].raw = 163
    node.sdo[0x1003][0].raw = 0

    # Transmit SYNC every 100 ms
    network.sync.start(0.1)
    
    node.setup_402_state_machine()
    
    device_name = node.sdo[0x1008].raw
    vendor_id = node.sdo[0x1018][1].raw
    
    print device_name
    print vendor_id
    
    node.powerstate_402.state = 'SWITCH ON DISABLED'
    
    print 'node state 3) = {0}'.format(node.nmt.state)

    # Read PDO configuration from node
    node.pdo.read()
    # Re-map TxPDO1
    node.pdo.tx[1].clear()
    node.pdo.tx[1].add_variable('Statusword')
    node.pdo.tx[1].add_variable('Velocity actual value')
    node.pdo.tx[1].trans_type = 254
    node.pdo.tx[1].event_timer = 10
    node.pdo.tx[1].enabled = True
    # Save new PDO configuration to node
    node.pdo.save()
    
    # publish the a value to the control word (in this case reset the fault at the motors)
    
    node.pdo.rx[1]['Controlword'].raw = 0x80
    node.pdo.rx[1].transmit()
    node.pdo.rx[1]['Controlword'].raw = 0x81
    node.pdo.rx[1].transmit()
    
    node.powerstate_402.state = 'READY TO SWITCH ON'
    node.powerstate_402.state = 'SWITCHED ON'
    
    node.pdo.export('database.dbc')
    
    # -----------------------------------------------------------------------------------------
    
    print ('Node booted up')
    
    # wait for heart beat
    # node.nmt.wait_for_heartbeat()
    
    node.powerstate_402.state = 'READY TO SWITCH ON'
    node.powerstate_402.state = 'SWITCHED ON'
    node.powerstate_402.state = 'OPERATION ENABLED'
    
    print 'Node Status {0}'.format(node.powerstate_402.state)
    
    # -----------------------------------------------------------------------------------------
    
    while True:
        node_guard = network.send_message(1827, None, True)
        try:    
            network.check()
        except:
            break
    
        # Read a value from TxPDO1
        node.pdo.tx[1].wait_for_reception()
        speed = node.pdo['Velocity actual value'].phys
        
        # Read the state of the Statusword
        statusword = node.sdo[0x6041].raw
        
        print 'statusword: {0}'.format(statusword)
        print 'VEL: {0}'.format(speed)
    
        time.sleep(0.01)

except KeyboardInterrupt:
    pass
except Exception as ex:
    print 'ERROR {0}'.format(ex)
finally:
    # Disconnect from CAN bus
    print 'going to exit... stoping...'
    if network:
        
        for node_id in network:
            node = network[node_id]
            node.nmt.state = 'PRE-OPERATIONAL'
        # network.send_message(0x0, [0x82, 0])
        # if node_guard:
        #    node_guard.stop()
        network.sync.stop()
        network.disconnect()

