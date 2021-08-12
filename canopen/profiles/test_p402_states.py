from canopen.objectdictionary import ObjectDictionary
from canopen.profiles.p402 import State402, BaseNode402


if __name__ == '__main__':
    n = BaseNode402(1, ObjectDictionary())

    for target_state in State402.SW_MASK:
        print('\n--- Target =', target_state, '---')
        for from_state in State402.SW_MASK:
            if target_state == from_state:
                continue
            if (from_state, target_state) in State402.TRANSITIONTABLE:
                print('direct:\t{} -> {}'.format(from_state, target_state))
            else:
                next_state = State402.next_state_for_enabling(from_state)
                if not next_state:
                    print('FAIL:\t{} -> {}'.format(from_state, next_state))
                else:
                    print('\t{} -> {} ...'.format(from_state, next_state))

            try:
                while from_state != target_state:
                    n.tpdo_values[0x6041] = State402.SW_MASK[from_state][1]
                    next_state = n._next_state(target_state)
                    print('\t\t-> {}'.format(next_state))
                    from_state = next_state
            except ValueError:
                print('\t\t-> disallowed!')
