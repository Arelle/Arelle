"""
See COPYRIGHT.md for copyright information.
"""

from typing import TYPE_CHECKING, Optional

from arelle.ModelValue import qname, QName, AnyURI
from arelle.PythonUtil import OrderedSet
from .XbrlConst import xbrl
from .ModelValueMore import SQName
from .XbrlProperty import XbrlProperty
from .XbrlTypes import XbrlModuleType, QNameKeyType, OptionalNonemptySet
from .XbrlObject import XbrlModelObject, XbrlReferencableModelObject, XbrlTaxonomyTagObject

class XbrlLabel(XbrlTaxonomyTagObject):
    module: XbrlModuleType
    relatedName: QName # (required) Defines a QName that the label is associated with.
    labelType: QName # (required) A QName representing the label type of the label. This can be a taxonomy defined label type or a standard XBRL label type defined in specification.
    language: str # (required) Defines the language of the label using a valid BCP 47 [BCP47] language code.
    value: str # (required) The text of the label.
    properties: OrderedSet[XbrlProperty] # (optional) ordered set of property objects used to specify additional properties associated with the concept using the property object. Only immutable properties as defined in the propertyType object can be added to a concept.

    @property
    def _type(self):
        return self.labelType

class XbrlLabelType(XbrlReferencableModelObject):
    module: XbrlModuleType
    name: QNameKeyType # (required) The name is a QName that uniquely identifies the label type object.
    uri: Optional[AnyURI] # (optional) A uri used to identify the label type of label objects for backward compatability with XBRL 2.1 taxonomies.
    dataType: QName # (required) Specifies the datatype of the value. The value MUST be a QName referencing either: - a built-in XML Schema simple type, - a datatype defined in this specification, - or a custom datatype defined in the taxonomy model.
    allowedObjects: OptionalNonemptySet[QName] # (optional) Defines an ordered set of object types that can use the labelType.  None means absent from input, empty set means [] on input which raises an error.

preferredLabel = qname(xbrl, "xbrl:preferredLabel")
