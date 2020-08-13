# inspired by the NmtMaster code
import logging
import time
from ..node import RemoteNode
from ..sdo import SdoCommunicationError

logger = logging.getLogger(__name__)

class State402(object):
    # Controlword (0x6040) commands
    CW_OPERATION_ENABLED = 0x0F
    CW_SHUTDOWN = 0x06
    CW_SWITCH_ON = 0x07
    CW_QUICK_STOP = 0x02
    CW_DISABLE_VOLTAGE = 0x00
    CW_SWITCH_ON_DISABLED = 0x80

    CW_CODE_COMMANDS = {
        CW_SWITCH_ON_DISABLED   : 'SWITCH ON DISABLED',
        CW_DISABLE_VOLTAGE      : 'DISABLE VOLTAGE',
        CW_SHUTDOWN             : 'READY TO SWITCH ON',
        CW_SWITCH_ON            : 'SWITCHED ON',
        CW_OPERATION_ENABLED    : 'OPERATION ENABLED',
        CW_QUICK_STOP           : 'QUICK STOP ACTIVE'
    }

    CW_COMMANDS_CODE = {
        'SWITCH ON DISABLED'    : CW_SWITCH_ON_DISABLED,
        'DISABLE VOLTAGE'       : CW_DISABLE_VOLTAGE,
        'READY TO SWITCH ON'    : CW_SHUTDOWN,
        'SWITCHED ON'           : CW_SWITCH_ON,
        'OPERATION ENABLED'     : CW_OPERATION_ENABLED,
        'QUICK STOP ACTIVE'     : CW_QUICK_STOP
    }

    # Statusword 0x6041 bitmask and values in the list in the dictionary value
    SW_MASK = {
        'NOT READY TO SWITCH ON': [0x4F, 0x00],
        'SWITCH ON DISABLED'    : [0x4F, 0x40],
        'READY TO SWITCH ON'    : [0x6F, 0x21],
        'SWITCHED ON'           : [0x6F, 0x23],
        'OPERATION ENABLED'     : [0x6F, 0x27],
        'FAULT'                 : [0x4F, 0x08],
        'FAULT REACTION ACTIVE' : [0x4F, 0x0F],
        'QUICK STOP ACTIVE'     : [0x6F, 0x07]
    }

    # Transition path to get to the 'OPERATION ENABLED' state
    NEXTSTATE2ENABLE = {
        ('START')                                                   : 'NOT READY TO SWITCH ON',
        ('FAULT', 'NOT READY TO SWITCH ON')                         : 'SWITCH ON DISABLED',
        ('SWITCH ON DISABLED')                                      : 'READY TO SWITCH ON',
        ('READY TO SWITCH ON')                                      : 'SWITCHED ON',
        ('SWITCHED ON', 'QUICK STOP ACTIVE', 'OPERATION ENABLED')   : 'OPERATION ENABLED',
        ('FAULT REACTION ACTIVE')                                   : 'FAULT'
    }

    # Tansition table from the DS402 State Machine
    TRANSITIONTABLE = {
        # disable_voltage ---------------------------------------------------------------------
        ('READY TO SWITCH ON', 'SWITCH ON DISABLED'):     CW_DISABLE_VOLTAGE,  # transition 7
        ('OPERATION ENABLED', 'SWITCH ON DISABLED'):      CW_DISABLE_VOLTAGE,  # transition 9
        ('SWITCHED ON', 'SWITCH ON DISABLED'):            CW_DISABLE_VOLTAGE,  # transition 10
        ('QUICK STOP ACTIVE', 'SWITCH ON DISABLED'):      CW_DISABLE_VOLTAGE,  # transition 12
        # automatic ---------------------------------------------------------------------------
        ('NOT READY TO SWITCH ON', 'SWITCH ON DISABLED'): 0x00,  # transition 1
        ('START', 'NOT READY TO SWITCH ON'):              0x00,  # transition 0
        ('FAULT REACTION ACTIVE', 'FAULT'):               0x00,  # transition 14
        # shutdown ----------------------------------------------------------------------------
        ('SWITCH ON DISABLED', 'READY TO SWITCH ON'):     CW_SHUTDOWN,  # transition 2
        ('SWITCHED ON', 'READY TO SWITCH ON'):            CW_SHUTDOWN,  # transition 6
        ('OPERATION ENABLED', 'READY TO SWITCH ON'):      CW_SHUTDOWN,  # transition 8
        # switch_on ---------------------------------------------------------------------------
        ('READY TO SWITCH ON', 'SWITCHED ON'):            CW_SWITCH_ON,  # transition 3
        ('OPERATION ENABLED', 'SWITCHED ON'):             CW_SWITCH_ON,  # transition 5
        # enable_operation --------------------------------------------------------------------
        ('SWITCHED ON', 'OPERATION ENABLED'):             CW_OPERATION_ENABLED,  # transition 4
        ('QUICK STOP ACTIVE', 'OPERATION ENABLED'):       CW_OPERATION_ENABLED,  # transition 16
        # quickstop ---------------------------------------------------------------------------
        ('READY TO SWITCH ON', 'QUICK STOP ACTIVE'):      CW_QUICK_STOP,  # transition 7
        ('SWITCHED ON', 'QUICK STOP ACTIVE'):             CW_QUICK_STOP,  # transition 10
        ('OPERATION ENABLED', 'QUICK STOP ACTIVE'):       CW_QUICK_STOP,  # transition 11
        # fault -------------------------------------------------------------------------------
        ('FAULT', 'SWITCH ON DISABLED'):                  CW_SWITCH_ON_DISABLED,  # transition 15
    }

    @staticmethod
    def next_state_for_enabling(_from):
        """Returns the next state needed for reach the state Operation Enabled
        :param string target: Target state
        :return string: Next target to chagne
        """
        for cond, next_state in State402.NEXTSTATE2ENABLE.items():
            if _from in cond:
                return next_state


class OperationMode(object):
    NO_MODE = 0
    PROFILED_POSITION = 1
    VELOCITY = 2
    PROFILED_VELOCITY = 3
    PROFILED_TORQUE = 4
    HOMING = 6
    INTERPOLATED_POSITION = 7
    CYCLIC_SYNCHRONOUS_POSITION = 8
    CYCLIC_SYNCHRONOUS_VELOCITY = 9
    CYCLIC_SYNCHRONOUS_TORQUE = 10
    OPEN_LOOP_SCALAR_MODE = -1
    OPEN_LOOP_VECTOR_MODE = -2

    CODE2NAME = {
        NO_MODE                     : 'NO MODE',
        PROFILED_POSITION           : 'PROFILED POSITION',
        VELOCITY                    : 'VELOCITY',
        PROFILED_VELOCITY           : 'PROFILED VELOCITY',
        PROFILED_TORQUE             : 'PROFILED TORQUE',
        HOMING                      : 'HOMING',
        INTERPOLATED_POSITION       : 'INTERPOLATED POSITION'
    }

    NAME2CODE = {
        'NO MODE'                       : NO_MODE,
        'PROFILED POSITION'             : PROFILED_POSITION,
        'VELOCITY'                      : VELOCITY,
        'PROFILED VELOCITY'             : PROFILED_VELOCITY,
        'PROFILED TORQUE'               : PROFILED_TORQUE,
        'HOMING'                        : HOMING,
        'INTERPOLATED POSITION'         : INTERPOLATED_POSITION
    }

    SUPPORTED = {
        'NO MODE'                     : 0x0,
        'PROFILED POSITION'           : 0x1,
        'VELOCITY'                    : 0x2,
        'PROFILED VELOCITY'           : 0x4,
        'PROFILED TORQUE'             : 0x8,
        'HOMING'                      : 0x20,
        'INTERPOLATED POSITION'       : 0x40
    }

class Homing(object):
    CW_START = 0x10
    CW_HALT = 0x100

    HM_ON_POSITIVE_FOLLOWING_ERROR = -8
    HM_ON_NEGATIVE_FOLLOWING_ERROR = -7
    HM_ON_POSITIVE_FOLLOWING_AND_INDEX_PULSE = -6
    HM_ON_NEGATIVE_FOLLOWING_AND_INDEX_PULSE = -5
    HM_ON_THE_POSITIVE_MECHANICAL_LIMIT = -4
    HM_ON_THE_NEGATIVE_MECHANICAL_LIMIT = -3
    HM_ON_THE_POSITIVE_MECHANICAL_LIMIT_AND_INDEX_PULSE = -2
    HM_ON_THE_NEGATIVE_MECHANICAL_LIMIT_AND_INDEX_PULSE = -1
    HM_NO_HOMING_OPERATION = 0
    HM_ON_THE_NEGATIVE_LIMIT_SWITCH_AND_INDEX_PULSE = 1
    HM_ON_THE_POSITIVE_LIMIT_SWITCH_AND_INDEX_PULSE = 2
    HM_ON_THE_POSITIVE_HOME_SWITCH_AND_INDEX_PULSE = [3, 4]
    HM_ON_THE_NEGATIVE_HOME_SWITCH_AND_INDEX_PULSE = [5, 6]
    HM_ON_THE_NEGATIVE_LIMIT_SWITCH = 17
    HM_ON_THE_POSITIVE_LIMIT_SWITCH = 18
    HM_ON_THE_POSITIVE_HOME_SWITCH = [19, 20]
    HM_ON_THE_NEGATIVE_HOME_SWITCH = [21, 22]
    HM_ON_NEGATIVE_INDEX_PULSE = 33
    HM_ON_POSITIVE_INDEX_PULSE = 34
    HM_ON_CURRENT_POSITION = 35

    STATES = {
    'IN PROGRESS'                  : [0x3400, 0x0000],
    'INTERRUPTED'                  : [0x3400, 0x0400],
    'ATTAINED'                     : [0x3400, 0x1000],
    'TARGET REACHED'               : [0x3400, 0x1400],
    'ERROR VELOCITY IS NOT ZERO'   : [0x3400, 0x2000],
    'ERROR VELOCITY IS ZERO'       : [0x3400, 0x2400]
    }


class BaseNode402(RemoteNode):
    """A CANopen CiA 402 profile slave node.

    :param int node_id:
        Node ID (set to None or 0 if specified by object dictionary)
    :param object_dictionary:
        Object dictionary as either a path to a file, an ``ObjectDictionary``
        or a file like object.
    :type object_dictionary: :class:`str`, :class:`canopen.ObjectDictionary`
    """

    def __init__(self, node_id, object_dictionary):
        super(BaseNode402, self).__init__(node_id, object_dictionary)
        self.tpdo_values = dict() # { index: TPDO_value }
        self.rpdo_pointers = dict() # { index: RPDO_pointer }

    def setup_402_state_machine(self):
        """Configure the state machine by searching for a TPDO that has the
        StatusWord mapped.
        :raise ValueError: If the the node can't find a Statusword configured
        in the any of the TPDOs
        """
        self.nmt.state = 'PRE-OPERATIONAL' # Why is this necessary?
        self.setup_pdos()
        self._check_controlword_configured()
        self._check_statusword_configured()
        self.nmt.state = 'OPERATIONAL'
        self.state = 'SWITCH ON DISABLED' # Why change state?

    def setup_pdos(self):
        self.pdo.read() # TPDO and RPDO configurations
        self._init_tpdo_values()
        self._init_rpdo_pointers()

    def _init_tpdo_values(self):
        for tpdo in self.tpdo.values():
            if tpdo.enabled:
                tpdo.add_callback(self.on_TPDOs_update_callback)
                for obj in tpdo:
                    logger.debug('Configured TPDO: {0}'.format(obj.index))
                    if obj.index not in self.tpdo_values:
                        self.tpdo_values[obj.index] = 0

    def _init_rpdo_pointers(self):
        # If RPDOs have overlapping indecies, rpdo_pointers will point to 
        # the first RPDO that has that index configured.
        for rpdo in self.rpdo.values():
            if rpdo.enabled:
                for obj in rpdo:
                    logger.debug('Configured RPDO: {0}'.format(obj.index))
                    if obj.index not in self.rpdo_pointers:
                        self.rpdo_pointers[obj.index] = obj

    def _check_controlword_configured(self):
        if 0x6040 not in self.rpdo_pointers: # Controlword
            logger.warning(
                "Controlword not configured in node {0}'s PDOs. Using SDOs can cause slow performance.".format(
                    self.id))

    def _check_statusword_configured(self):
        if 0x6041 not in self.tpdo_values: # Statusword
            raise ValueError(
                "Statusword not configured in node {0}'s PDOs. Using SDOs can cause slow performance.".format(
                    self.id))

    def reset_from_fault(self):
        """Reset node from fault and set it to Operation Enable state
        """
        if self.state == 'FAULT':
            # Resets the Fault Reset bit (rising edge 0 -> 1)
            self.controlword = State402.CW_DISABLE_VOLTAGE
            timeout = time.time() + 0.4  # 400 ms
            
            while self.is_faulted():
                if time.time() > timeout:
                    break
                time.sleep(0.01)  # 10 ms
            self.state = 'OPERATION ENABLED'
    
    def is_faulted(self):
        return self.statusword & State402.SW_MASK['FAULT'][0] == State402.SW_MASK['FAULT'][1]

    def homing(self, timeout=30, set_new_home=True):
        """Function to execute the configured Homing Method on the node
        :param int timeout: Timeout value (default: 30)
        :param bool set_new_home: Defines if the node should set the home offset
        object (0x607C) to the current position after the homing procedure (default: true)
        :return: If the homing was complete with success
        :rtype: bool
        """
        previus_op_mode = self.op_mode
        self.state = 'SWITCHED ON'
        self.op_mode = 'HOMING'
        # The homing process will initialize at operation enabled
        self.state = 'OPERATION ENABLED'
        homingstatus = 'IN PROGRESS'
        self.controlword = State402.CW_OPERATION_ENABLED | Homing.CW_START
        t = time.time() + timeout
        try:
            while homingstatus not in ('TARGET REACHED', 'ATTAINED'):
                for key, value in Homing.STATES.items():
                    # check if the value after applying the bitmask (value[0])
                    # corresponds with the value[1] to determine the current status
                    bitmaskvalue = self.statusword & value[0]
                    if bitmaskvalue == value[1]:
                        homingstatus = key
                if homingstatus in ('INTERRUPTED', 'ERROR VELOCITY IS NOT ZERO', 'ERROR VELOCITY IS ZERO'):
                    raise  RuntimeError ('Unable to home. Reason: {0}'.format(homingstatus))
                time.sleep(0.001)
                if time.time() > t:
                    raise RuntimeError('Unable to home, timeout reached')
            if set_new_home:
                actual_position = self.sdo[0x6063].raw
                self.sdo[0x607C].raw = actual_position # home offset (0x607C)
                logger.info('Homing offset set to {0}'.format(actual_position))
            logger.info('Homing mode carried out successfully.')
            return True
        except RuntimeError as e:
            logger.info(str(e))
        finally:
            self.op_mode = previus_op_mode
        return False

    @property
    def op_mode(self):
        """
        :return: Return the operation mode stored in the object 0x6061 through SDO
        :rtype: int
        """
        return OperationMode.CODE2NAME[self.sdo[0x6061].raw]

    @op_mode.setter
    def op_mode(self, mode):
        """Function to define the operation mode of the node
        :param string mode: Mode to define.
        :return: Return if the operation mode was set with success or not
        :rtype: bool

        The modes can be:
        - 'NO MODE'
        - 'PROFILED POSITION'
        - 'VELOCITY'
        - 'PROFILED VELOCITY'
        - 'PROFILED TORQUE'
        - 'HOMING'
        - 'INTERPOLATED POSITION'
        - 'CYCLIC SYNCHRONOUS POSITION'
        - 'CYCLIC SYNCHRONOUS VELOCITY'
        - 'CYCLIC SYNCHRONOUS TORQUE'
        - 'OPEN LOOP SCALAR MODE'
        - 'OPEN LOOP VECTOR MODE'
        """
        try:
            if not self.is_op_mode_supported(mode):
                raise TypeError(
                    'Operation mode {0} not suppported on node {1}.'.format(mode, self.id))

            start_state = self.state

            if self.state == 'OPERATION ENABLED':
                self.state = 'SWITCHED ON' 
                # ensure the node does not move with an old value
                self._clear_target_values() # Shouldn't this happen before it's switched on?
                
            # operation mode
            self.sdo[0x6060].raw = OperationMode.NAME2CODE[mode]

            timeout = time.time() + 0.5 # 500 ms
            while self.op_mode != mode:
                if time.time() > timeout:
                    raise RuntimeError(
                        "Timeout setting node {0}'s new mode of operation to {1}.".format(
                            self.id, mode))
            return True
        except SdoCommunicationError as e:
            logger.warning('[SDO communication error] Cause: {0}'.format(str(e)))
        except (RuntimeError, ValueError) as e:
            logger.warning('{0}'.format(str(e)))
        finally:
            self.state = start_state # why?
            logger.info('Set node {n} operation mode to {m}.'.format(n=self.id , m=mode))
        return False

    def _clear_target_values(self):
        # [target velocity, target position, target torque]
        for target_index in [0x60FF, 0x607A, 0x6071]:
            if target_index in self.sdo.keys():
                self.sdo[target_index].raw = 0

    def is_op_mode_supported(self, mode):
        """Function to check if the operation mode is supported by the node
        :param int mode: Operation mode
        :return: If the operation mode is supported
        :rtype: bool
        """
        mode_support = self.sdo[0x6502].raw & OperationMode.SUPPORTED[mode]
        return mode_support == OperationMode.SUPPORTED[mode]

    def on_TPDOs_update_callback(self, mapobject):
        """This function receives a map object.
        this map object is then used for changing the
        :param mapobject: :class: `canopen.objectdictionary.Variable`
        """
        for obj in mapobject:
            self.tpdo_values[obj.index] = obj.raw

    @property
    def statusword(self):
        """Returns the last read value of the Statusword (0x6041) from the device.
        If the the object 0x6041 is not configured in any TPDO it will fallback to the SDO mechanism
        and try to tget the value.
        """
        try:
            return self.tpdo_values[0x6041]
        except KeyError:
            logger.warning('The object 0x6041 is not a configured TPDO, fallback to SDO')
            return self.sdo[0x6041].raw

    @property
    def controlword(self):
        raise RuntimeError('The Controlword is write-only.')

    @controlword.setter
    def controlword(self, value):
        """Send the state using PDO or SDO objects.
        :param int value: State value to send in the message
        """
        if 0x6040 in self.rpdo_pointers:
            self.rpdo_pointers[0x6040].raw = value
            self.rpdo_pointers[0x6040].pdo_parent.transmit()
        else:
            self.sdo[0x6040].raw = value

    @property
    def state(self):
        """Attribute to get or set node's state as a string for the DS402 State Machine.
        States of the node can be one of:
        - 'NOT READY TO SWITCH ON'
        - 'SWITCH ON DISABLED'
        - 'READY TO SWITCH ON'
        - 'SWITCHED ON'
        - 'OPERATION ENABLED'
        - 'FAULT'
        - 'FAULT REACTION ACTIVE'
        - 'QUICK STOP ACTIVE'
        """
        for state, mask_val_pair in State402.SW_MASK.items():
            mask = mask_val_pair[0]
            state_value = mask_val_pair[1]
            masked_value = self.statusword & mask
            if masked_value == state_value:
                return state
        return 'UNKNOWN'

    @state.setter
    def state(self, target_state):
        """ Defines the state for the DS402 state machine
        States to switch to can be one of:
        - 'SWITCH ON DISABLED'
        - 'DISABLE VOLTAGE'
        - 'READY TO SWITCH ON'
        - 'SWITCHED ON'
        - 'OPERATION ENABLED'
        - 'QUICK STOP ACTIVE'
        :param string target_state: Target state
        :raise RuntimeError: Occurs when the time defined to change the state is reached
        :raise ValueError: Occurs when trying to execute a ilegal transition in the sate machine
        """
        timeout = time.time() + 0.8 # 800 ms
        while self.state != target_state:
            next_state = self._next_state(target_state)
            if self._change_state(next_state):
                continue       
            if time.time() > timeout:
                raise RuntimeError('Timeout when trying to change state')
            time.sleep(0.01) # 10 ms

    def _next_state(self, target_state):
        if target_state == 'OPERATION ENABLED':
            return State402.next_state_for_enabling(self.state)
        else:
            return target_state

    def _change_state(self, target_state):
        try:
            self.controlword = State402.TRANSITIONTABLE[(self.state, target_state)]
        except KeyError:
            raise ValueError(
                'Illegal state transition from {f} to {t}'.format(f=self.state, t=target_state))
        timeout = time.time() + 0.4 # 400 ms
        while self.state != target_state:
            if time.time() > timeout:
                return False
            time.sleep(0.01) # 10 ms
        return True
