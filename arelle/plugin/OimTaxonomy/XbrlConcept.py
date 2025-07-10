"""
See COPYRIGHT.md for copyright information.
"""

from typing import TYPE_CHECKING, Optional, Any
from typing_extensions import TypeAlias
from decimal import Decimal

from arelle.ModelValue import QName
from arelle.PythonUtil import OrderedSet
from arelle.XbrlConst import xsd, isNumericXsdType
from .XbrlProperty import XbrlProperty
from .XbrlTypes import XbrlTaxonomyModuleType, QNameKeyType
from .XbrlObject import XbrlTaxonomyObject, XbrlReferencableTaxonomyObject
from arelle.FunctionFn import true

XbrlUnitTypeType: TypeAlias = "XbrlUnitType"

class XbrlConcept(XbrlReferencableTaxonomyObject):
    taxonomy: XbrlTaxonomyModuleType
    name: QNameKeyType # (required) The name is a QName that uniquely identifies the concept object.
    dataType: QName # (required) Indicates the dataType of the concept. These are provided as a QName based on the datatypes specified in the XBRL 2.1 specification and any custom datatype defined in the taxonomy.
    periodType: str # (required) Indicates the period type of the concept. The property values can be either instant or duration. If the concept can be an atemporal value it must be defined as a duration. (i.e. the value does not change with the passage of time)
    enumerationDomain: Optional[QName] # (optional) Used to specify enumerated domain members that are associated with a domain defined in the taxonomy.
    nillable: Optional[bool] # (optional) Used to specify if the concept can have a nill value. The default value is true.
    properties: OrderedSet[XbrlProperty] # (optional) ordered set of property objects used to specify additional properties associated with the concept using the property object. Only immutable properties as defined in the propertyType object can be added to a concept.

    def isNumeric(self, txmyMdl):
        dtObj = txmyMdl.namedObjects.get(self.dataType)
        return isinstance(dtObj, XbrlDataType) and dtObj.isNumeric(txmyMdl)

    def isOimTextFactType(self, txmyMdl):
        dtObj = txmyMdl.namedObjects.get(self.dataType)
        return isinstance(dtObj, XbrlDataType) and dtObj.isOimTextFactType(txmyMdl)


class XbrlDataType(XbrlReferencableTaxonomyObject):
    taxonomy: XbrlTaxonomyModuleType
    name: QNameKeyType # (required) The name is a QName that uniquely identifies the datatype object.
    baseType: QName # (required) The base type is a QName that uniquely identifies the base datatype the datatype is based on.
    enumeration: OrderedSet[Any] # (optional) Defines an ordered set of enumerated values of the datatype if applicable
    minInclusive: Optional[Decimal] # (optional) Defines a decimal value to indicate a min inclusive cardinal value for a type. Only applies to types based on float, double and decimal.
    maxInclusive: Optional[Decimal] # (optional) Defines a decimal value to indicate a max inclusive cardinal value for a type. Only applies to types based on float, double and decimal.
    minExclusive: Optional[Decimal] # (optional) Defines a decimal value to indicate a min exclusive cardinal value for a type. Only applies to types based on float, double and decimal.
    maxExclusive: Optional[Decimal] # (optional) Defines a decimal value to indicate a max exclusive cardinal value for a type. Only applies to types based on float, double and decimal.
    totalDigits: Optional[int] # (optional) Defines an int value to indicate total digits of a value. Only applies to types based on float, double and decimal.
    fractionDigits: Optional[int] # (optional) Defines an int of digits to the right of the decimal place. Only applies to types based on float, double and decimal.
    length: Optional[int] # (optional) Defines an int value used to define the length of a string value.
    minLength: Optional[int] # (optional) Defines an int used to define minimum length of a string value.
    maxLength: Optional[int] # (optional) Defines an int used to define maximum length of a string value.
    whiteSpace: Optional[str] # (optional) Defines a string one of preserve, replace or collapse.
    patterns: set[str] # (optional) Defines a string as a single regex expressions. At least one of the regex patterns must match. (Uses XML regex)
    unitTypes: OrderedSet[XbrlUnitTypeType] # unitType comprising a dataType expressed as a value of the datatype. For example xbrli:flow has unit datatypes of xbrli:volume and xbrli:time

    def xsBaseType(self, txmyMdl, visitedTypes=None): # find base types thru dataType hierarchy
        try:
            return self._xsBaseType
        except AttributeError:
            if not visitedTypes: visitedTypes = set() # might be a loop
            if self.baseType.namespaceURI == xsd:
                self._xsBaseType = self.baseType.localName
                return self._xsBaseType
            elif self not in visitedTypes:
                visitedTypes.add(self)
                baseTypeObj = txmyMdl.namedObjects.get(self.baseType)
                if isinstance(baseTypeObj, XbrlDataType):
                    self._xsBaseType = baseTypeObj.xsBaseType(txmyMdl, visitedTypes)
                    return self._xsBaseType
                visitedTypes.remove(self)
            self._xsBaseType = None
            return None

    def isNumeric(self, txmyMdl):
        return isNumericXsdType(self.xsBaseType(txmyMdl))

    def instanceOfType(self, qnTypes, txmyMdl, visitedTypes=None):
        if isinstance(qnTypes, (tuple,list,set)):
            if self.name in qnTypes:
                return True
        elif self.name == qnTypes:
            return True
        if not visitedTypes: visitedTypes = set() # might be a loop
        if self not in visitedTypes:
            visitedTypes.add(self)
            baseTypeObj = txmyMdl.namedObjects.get(self.baseType)
            if isinstance(baseTypeObj, XbrlDataType):
                if baseTypeObj.instanceOfType(qnTypes, txmyMdl, visitedTypes):
                    return True
            visitedTypes.remove(self)
        return False

    def xsFacets(self):
        facets = {}
        for facet in ("enumeration", "minInclusive", "maxInclusive", "minExclusive", "maxExclusive", "totalDigits", "fractionDigits", "length", "minLength", "maxLength", "whiteSpace", "patterns"):
            value = getattr(self, facet, None)
            if value is not None and not(isinstance(value, (set,list,OrderedSet)) and not value):
                facets[facet] = value
        return facets

    def isOimTextFactType(self):
        """(str) -- True if type meets OIM requirements to be a text fact"""
        if self.modelDocument.targetNamespace.startswith(XbrlConst.dtrTypesStartsWith):
            return self.name not in XbrlConst.dtrNoLangItemTypeNames and self.baseXsdType in XbrlConst.xsdStringTypeNames
        if self.modelDocument.targetNamespace == XbrlConst.xbrli:
            return self.baseXsdType not in XbrlConst.xsdNoLangTypeNames and self.baseXsdType in XbrlConst.xsdStringTypeNames
        qnameDerivedFrom = self.qnameDerivedFrom
        if not isinstance(qnameDerivedFrom, ModelValue.QName): # textblock not a union type
            return False
        typeDerivedFrom = self.xbrlTxmyMdl.namedObjects.get(baseType)
        return typeDerivedFrom.isOimTextFactType if typeDerivedFrom is not None else False

class XbrlUnitType(XbrlTaxonomyObject):
    dataTypeNumerator: Optional[XbrlDataType] # (optional) Defines the numerator datatype of of the datatype
    dataTypeDenominator: Optional[XbrlDataType] # (optional) Defines the denominator datatype used by a unit used to define a value of the datatype
    dataTypeMutiplier: Optional[XbrlDataType] # (optional) Defines a mutiplier datatype used by a unit used to define a value of the datatype
