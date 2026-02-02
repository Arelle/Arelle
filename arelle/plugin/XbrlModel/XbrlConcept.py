"""
See COPYRIGHT.md for copyright information.
"""

from typing import TYPE_CHECKING, Union, Optional, Any
from typing_extensions import TypeAlias
from decimal import Decimal

from arelle.ModelValue import QName
from arelle.PythonUtil import OrderedSet
from arelle.XbrlConst import xsd, isNumericXsdType
from .XbrlProperty import XbrlProperty
from .XbrlTypes import XbrlModuleType, QNameKeyType, DefaultTrue, DefaultFalse
from .XbrlObject import XbrlModelObject, XbrlReferencableModelObject
from arelle.FunctionFn import true
xbrlObjectQNames = None

class XbrlConcept(XbrlReferencableModelObject):
    module: XbrlModuleType
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

class XbrlCollectionType(XbrlModelObject):
    dataTypesAllowed: OrderedSet[QName] # (required) Defines a set of data types that can be included in the set. The data types are defined using the QName of the dataType object.
    uniqueValues: Union[bool, DefaultTrue] # (optional) Indicates if the values in the set must be unique. If true all values in the set must be unique. If false values can be duplicated. Defaults to true if not provided.
    orderedValues: Union[bool, DefaultFalse] # (optional) Indicates if the values in the set are ordered. If true the order of the values in the set is significant. If false the order of the values in the set is not significant. Defaults to false if not provided.

class XbrlUnitType(XbrlModelObject):
    dataTypeNumerator: Optional[QName] # (optional) Defines the numerator data type of the data type.
    dataTypeDenominator: Optional[QName] # (optional) Defines the denominator data type used by a unit used to define a value of the data type.
    dataTypeMultiplier: Optional[QName] # (optional) Defines a multiplier data type used by a unit used to define a value of the data type.

class XbrlDataType(XbrlReferencableModelObject):
    module: XbrlModuleType  
    name: QNameKeyType # (required) The name is a QName that uniquely identifies the datatype object.
    baseType: QName # (required) The base type is a QName that uniquely identifies the base datatype the datatype is based on.
    enumeration: OrderedSet[Any] # (optional) Defines an ordered set of enumerated values of the datatype if applicable
    collectionType: Optional[XbrlCollectionType] # (optional) Defines a set of of data types that can be used in a set. This attribute can only be used when the base type is defined as a xbrli:set.
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
    unitType: Optional[XbrlUnitType] # (optional) Defines a unitType object For example xbrli:flow has unit datatypes of xbrli:volume and xbrli:time
    allowedObjects: set[QName] # (optional) Set of object type QNames that the data type can be used with. If no value is provided the property can be used with any object. The value provided is a set of model component objects.

    def xsBaseType(self, compMdl, visitedTypes=None): # find base types thru dataType hierarchy
        try:
            return self._xsBaseType
        except AttributeError:
            if not visitedTypes: visitedTypes = set() # might be a loop
            if self.name.namespaceURI == xsd: # this is a base type
                self._xsBaseType = self.name.localName
                return self._xsBaseType
            # below finds an xs-derived more-base type but shouldn' return xs:anyType
            #if self.baseType.namespaceURI == xsd:
            #    self._xsBaseType = self.baseType.localName
            #    return self._xsBaseType
            elif self not in visitedTypes:
                visitedTypes.add(self)
                baseTypeObj = compMdl.namedObjects.get(self.baseType)
                if isinstance(baseTypeObj, XbrlDataType):
                    self._xsBaseType = baseTypeObj.xsBaseType(compMdl, visitedTypes)
                    return self._xsBaseType
                visitedTypes.remove(self)
            self._xsBaseType = None
            return None

    def isAllowedFor(self, obj): # obj may be a QName or instance of object
        global xbrlObjectQNames
        if xbrlObjectQNames is None:
            from .XbrlModule import xbrlObjectQNames
        if not self.allowedObjects:
            return True
        if isinstance(obj, QName):
            qn = obj
        else:
            qn = xbrlObjectQNames.get(type(obj))
        return qn in self.allowedObjects

    def isNumeric(self, compMdl):
        return isNumericXsdType(self.xsBaseType(compMdl))

    def instanceOfType(self, qnTypes, compMdl, visitedTypes=None):
        if isinstance(qnTypes, (tuple,list,set)):
            if self.name in qnTypes:
                return True
        elif self.name == qnTypes:
            return True
        if not visitedTypes: visitedTypes = set() # might be a loop
        if self not in visitedTypes:
            visitedTypes.add(self)
            baseTypeObj = compMdl.namedObjects.get(self.baseType)
            if isinstance(baseTypeObj, XbrlDataType):
                if baseTypeObj.instanceOfType(qnTypes, compMdl, visitedTypes):
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
        typeDerivedFrom = self.xbrlCompMdl.namedObjects.get(baseType)
        return typeDerivedFrom.isOimTextFactType if typeDerivedFrom is not None else False
