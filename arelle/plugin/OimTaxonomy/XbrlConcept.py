"""
See COPYRIGHT.md for copyright information.
"""

from typing import TYPE_CHECKING, Set

from arelle.ModelValue import QName
from arelle.PythonUtil import OrderedSet
from .XbrlDts import XbrlDts

class XbrlConcept:
    def __init__(self,
                 xbrlTaxonomy: XbrlTaxonomy,
                 name: QName,
                 dataType: QName,
                 periodType: QName):
        self.xbrlTaxonomy: XbrlTaxonomy = xbrlTaxonomy
        self.name: QName = name # (required) The name is a QName that uniquely identifies the concept object.
        self.dataType: QName = dataType # (required) Indicates the dataType of the concept. These are provided as a QName based on the datatypes specified in the XBRL 2.1 specification and any custom datatype defined in the taxonomy.
        self.periodType: QName = periodType # (required) Indicates the period type of the concept. The property values can be either instant or duration. If the concept can be an atemporal value it must be defined as a duration. (i.e. the value does not change with the passage of time)
        self.enumerationDomain: QName | None = None # (optional) Used to specify enumerated domain members that are associated with a domain defined in the taxonomy.
        self.nillable: bool = True # (optional) Used to specify if the concept can have a nill value. The default value is true.
        self.properties: OrderedSet(XbrlProperty) = OrderedSet() # (optional) ordered set of property objects used to specify additional properties associated with the concept using the property object. Only immutable properties as defined in the propertyType object can be added to a concept.
