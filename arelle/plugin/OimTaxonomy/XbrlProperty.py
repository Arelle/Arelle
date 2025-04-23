"""
See COPYRIGHT.md for copyright information.
"""

from typing import TYPE_CHECKING, Any, Optional

from arelle.ModelValue import QName
from arelle.PythonUtil import OrderedSet
from .XbrlTaxonomyObject import XbrlTaxonomyObject

class XbrlProperty:
    propertyTypeName: QName # (required) The name is a QName that uniquely identifies the property type object.
    propertyValue: Any # (required) The value of the property, that must be consistent with the datatype of the property.

    @property
    def propertyView(self):
        return ( str(getattr(self, "propertyTypeName", "")), str(getattr(self, "propertyValue", "")) )


class XbrlPropertyType(XbrlTaxonomyObject):
    name: QName # (required) The name is a QName that uniquely identifies the property type object.
    dataType: QName # (required) Indicates the dataType of the property value. These are provided as a QName based on the datatypes specified in the XBRL 2.1 specification and any custom datatype defined in the taxonomy.
    enumerationDomain: Optional[QName] # (optional) Used to specify the QName of a domain object that is used to derive enumerated domain members QNames that can be used for the property.
    immutable: bool # (required) Indicates if the property is immutable. If changes to the property change the meaning of the object it is immutable, if it provides extra information about the object it is mutable.
    allowedObjects: set[QName] # (optional) List of allowable objects that the property can be used with. For example the balance property can only be used with concept objects.
