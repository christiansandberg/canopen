Object Dictionary
=================

CANopen devices must have an object dictionary, which is used for configuration
and communication with the device.
An entry in the object dictionary is defined by:

* Index, the 16-bit address of the object in the dictionary
* Object type, such as an array, record, or simple variable
* Name, a string describing the entry
* Type, gives the datatype of the variable
  (or the datatype of all variables of an array)
* Attribute, which gives information on the access rights for this entry,
  this can be read/write (rw), read-only (ro) or write-only (wo)

The basic datatypes for object dictionary values such as booleans, integers and
floats are defined in the standard, as well as composite datatypes such as
strings, arrays and records. The composite datatypes can be subindexed with an
8-bit index; the value in subindex 0 of an array or record indicates the number
of elements in the data structure, and is of type UNSIGNED8.


Supported formats
-----------------

The currently supported file formats for specifying a node's object dictionary
are:

* EDS (standardized INI-file like format)
* EPF (proprietary XML-format used by Inmotion Technologies) 


Examples
--------

The object dictionary file is normally provided when creating a node.
Here is an example where the entire object dictionary gets printed out::

    node = network.add_node(6, 'od.eds')
    for obj in node.object_dictionary.values():
        print('0x%X: %s' % (obj.index, obj.name))
        if isinstance(obj, canopen.objectdictionary.Record):
            for subobj in obj.values():
                print('  %d: %s' % (subobj.subindex, subobj.name))

You can access the objects using either index/subindex or names::

    device_name_obj = node.object_dictionary['ManufacturerDeviceName']
    vendor_id_obj = node.object_dictionary[0x1018][1]


API
---

.. autofunction:: canopen.import_od

.. autoclass:: canopen.ObjectDictionary
   :members:

.. autoclass:: canopen.objectdictionary.Variable
   :members:

.. autoclass:: canopen.objectdictionary.Record
   :members:

.. autoclass:: canopen.objectdictionary.Array
   :members:

Exceptions
~~~~~~~~~~

.. autoexception:: canopen.ObjectDictionaryError
   :members:
