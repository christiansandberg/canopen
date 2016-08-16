import xml.etree.ElementTree as etree
from canopen import objectdictionary


DATA_TYPES = {
    "INTEGER8": objectdictionary.INTEGER8,
    "INTEGER16": objectdictionary.INTEGER16,
    "INTEGER32": objectdictionary.INTEGER32,
    "UNSIGNED8": objectdictionary.UNSIGNED8,
    "UNSIGNED16": objectdictionary.UNSIGNED16,
    "UNSIGNED32": objectdictionary.UNSIGNED32,
    "REAL32": objectdictionary.REAL32,
    "VISIBLE_STRING": objectdictionary.VIS_STR
}


def import_epf(filename):
    od = objectdictionary.ObjectDictionary()
    tree = etree.parse(filename).getroot()

    # Parse Object Dictionary
    for group_tree in tree.iterfind("Dictionary/Parameters/Group"):
        name = group_tree.get("SymbolName")
        index = int(group_tree.find("Parameter").get("Index"), 0)
        group = objectdictionary.Group(index, name)
        od.add_group(group)

        for par_tree in group_tree.iter("Parameter"):
            if par_tree.get("ObjectType") == "ARRAY":
                group.is_array = True
            subindex = int(par_tree.get("SubIndex"))
            name = par_tree.get("SymbolName")
            data_type = par_tree.get("DataType")

            par = objectdictionary.Parameter(subindex, name)
            par.factor = float(par_tree.get("Factor", 1.0))
            par.unit = par_tree.get("Unit", "")
            par.data_type = DATA_TYPES[data_type]
            try:
                par.min = int(par_tree.get("MinimumValue"))
            except (ValueError, TypeError):
                pass
            try:
                par.max = int(par_tree.get("MaximumValue"))
            except (ValueError, TypeError):
                pass

            # Find value descriptions
            for value_field_def in par_tree.iterfind("ValueFieldDefs/ValueFieldDef"):
                value = int(value_field_def.get("Value"), 0)
                desc = value_field_def.get("Description")
                par.add_value_description(value, desc)

            if par_tree.get("ObjectType") == "ARRAY":
                group.is_array = True

            group.add_parameter(par)

    return od
