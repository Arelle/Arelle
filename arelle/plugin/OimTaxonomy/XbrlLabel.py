"""
See COPYRIGHT.md for copyright information.
"""

from typing import TYPE_CHECKING, Optional

from arelle.ModelValue import QName, AnyURI
from arelle.PythonUtil import OrderedSet
from .ModelValueMore import SQName
from .XbrlProperty import XbrlProperty
from .XbrlTypes import XbrlTaxonomyType, QNameKeyType
from .XbrlTaxonomyObject import XbrlTaxonomyObject, XbrlReferencableTaxonomyObject, XbrlTaxonomyTagObject

class XbrlLabel(XbrlTaxonomyTagObject):
    taxonomy: XbrlTaxonomyType
    relatedName: QName # (required) Defines a QName that the label is associated with.
    labelType: QName # (required) A QName representing the label type of the label. This can be a taxonomy defined label type or a standard XBRL label type defined in specification.
    language: str # (required) Defines the language of the label using a valid BCP 47 [BCP47] language code.
    value: str # (required) The text of the label.
    properties: OrderedSet[XbrlProperty] # (optional) ordered set of property objects used to specify additional properties associated with the concept using the property object. Only immutable properties as defined in the propertyType object can be added to a concept.

    @property
    def _type(self):
        return self.labelType

class XbrlLabelType(XbrlReferencableTaxonomyObject):
    taxonomy: XbrlTaxonomyType
    name: QNameKeyType # (required) The name is a QName that uniquely identifies the label type object.
    uri: Optional[AnyURI] # (optional) A uri used to identify the label type of label objects for backward compatability with XBRL 2.1 taxonomies.
    dataType: Optional[AnyURI] # (optional) Indicates the dataType of the label object value property. This allows the value of the label to be constrained if required.
    allowedObjects: OrderedSet[QName] # (optional) Defines an ordered set of object types that can use the labelType.
