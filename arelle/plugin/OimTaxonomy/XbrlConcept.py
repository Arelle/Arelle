"""
See COPYRIGHT.md for copyright information.
"""

from typing import TYPE_CHECKING, TypeAlias, Optional, Any
from decimal import Decimal

from arelle.ModelValue import QName
from arelle.PythonUtil import OrderedSet
from .XbrlProperty import XbrlProperty
from .XbrlTypes import XbrlTaxonomyType, QNameKeyType
from .XbrlTaxonomyObject import XbrlReferencableTaxonomyObject

XbrlUnitTypeType: TypeAlias = "XbrlUnitType"

class XbrlConcept(XbrlReferencableTaxonomyObject):
    taxonomy: XbrlTaxonomyType
    name: QNameKeyType # (required) The name is a QName that uniquely identifies the concept object.
    dataType: QName # (required) Indicates the dataType of the concept. These are provided as a QName based on the datatypes specified in the XBRL 2.1 specification and any custom datatype defined in the taxonomy.
    periodType: str # (required) Indicates the period type of the concept. The property values can be either instant or duration. If the concept can be an atemporal value it must be defined as a duration. (i.e. the value does not change with the passage of time)
    enumerationDomain: Optional[QName] # (optional) Used to specify enumerated domain members that are associated with a domain defined in the taxonomy.
    nillable: Optional[bool] # (optional) Used to specify if the concept can have a nill value. The default value is true.
    properties: OrderedSet[XbrlProperty] # (optional) ordered set of property objects used to specify additional properties associated with the concept using the property object. Only immutable properties as defined in the propertyType object can be added to a concept.

class XbrlDataType(XbrlReferencableTaxonomyObject):
    taxonomy: XbrlTaxonomyType
    name: QNameKeyType # (required) The name is a QName that uniquely identifies the datatype object.
    baseType: QName # (required) The base type is a QName that uniquely identifies the base datatype the datatype is based on.
    enumeration: OrderedSet[Any] # (optional) Defines an ordered set of enumerated values of the datatype if applicable
    minInclusive: Optional[Decimal] # (optional) Defines a decimal value to indicate a min inclusive cardinal value for a type. Only applies to types based on float, double and decimal.
    maxInclusive: Optional[Decimal] # (optional) Defines a decimal value to indicate a max inclusive cardinal value for a type. Only applies to types based on float, double and decimal.
    minExclusive: Optional[Decimal] # (optional) Defines a decimal value to indicate a min exclusive cardinal value for a type. Only applies to types based on float, double and decimal.
    maxExclusive: Optional[Decimal] # (optional) Defines a decimal value to indicate a max exclusive cardinal value for a type. Only applies to types based on float, double and decimal.
    totalDigits: int # (optional) Defines an int value to indicate total digits of a value. Only applies to types based on float, double and decimal.
    fractionDigits: int # (optional) Defines an int of digits to the right of the decimal place. Only applies to types based on float, double and decimal.
    length: int # (optional) Defines an int value used to define the length of a string value.
    minLength: int # (optional) Defines an int used to define minimum length of a string value.
    maxLength: int # (optional) Defines an int used to define maximum length of a string value.
    whiteSpace: Optional[str] # (optional) Defines a string one of preserve, replace or collapse.
    pattern: set[str] # (optional) Defines a string as a single regex expressions. At least one of the regex patterns must match. (Uses XML regex)
    unitTypes: OrderedSet[XbrlUnitTypeType] # unitType comprising a dataType expressed as a value of the datatype. For example xbrli:flow has unit datatypes of xbrli:volume and xbrli:time

class XbrlUnitType(XbrlReferencableTaxonomyObject):
    taxonomy: XbrlTaxonomyType
    relatedName: QNameKeyType # (required) Defines a QName that the label is associated with.
    dataTypeNumerator: Optional[XbrlDataType] # (optional) Defines the numerator datatype of of the datatype
    dataTypeDenominator: Optional[XbrlDataType] # (optional) Defines the denominator datatype used by a unit used to define a value of the datatype
    dataTypeMutiplier: Optional[XbrlDataType] # (optional) Defines a mutiplier datatype used by a unit used to define a value of the datatype
